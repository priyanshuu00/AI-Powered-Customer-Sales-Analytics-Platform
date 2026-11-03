"""Live data tests: SQLite store, ETL-to-dashboard sync, uploads, simulation."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import dashboard.database as dashboard_database
from etl import sqlite_store
from etl.config import FILE_PATHS
from etl.pipeline import run_pipeline
from etl.sample_data import build_sample_frames, seed_sample_raw_csvs
from etl.sqlite_store import (
    VIEW_COLUMNS,
    VIEW_KEYS,
    VIEW_SQL_NAMES,
    derive_views,
    ensure_sqlite_store,
    read_sqlite_views,
    simulate_orders,
    views_from_dataframe,
)
from etl.transform import transform_data


class LiveDataTestCase(unittest.TestCase):
    """Each test gets an isolated SQLite file and a forced-offline MySQL."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "analytics_live.db"

        self._env = patch.dict(
            os.environ, {"ANALYTICS_SQLITE_PATH": str(self.db_path)}
        )
        self._env.start()

        self._probe = patch.object(
            dashboard_database,
            "_probe_mysql",
            side_effect=RuntimeError("mysql offline in tests"),
        )
        self._probe.start()

        dashboard_database.clear_custom_views()
        dashboard_database.reset_data_source()

    def tearDown(self) -> None:
        dashboard_database.clear_custom_views()
        sqlite_store.dispose_sqlite_engines(self.db_path)
        self._probe.stop()
        self._env.stop()
        self._tmp.cleanup()


class TestDerivedViews(LiveDataTestCase):
    def test_sample_etl_derives_all_five_schemas(self):
        views = derive_views(transform_data(build_sample_frames()))

        self.assertEqual(set(views), set(VIEW_KEYS))
        for key, columns in VIEW_COLUMNS.items():
            with self.subTest(view=key):
                self.assertTrue(
                    set(columns) <= set(views[key].columns),
                    f"{key} is missing {set(columns) - set(views[key].columns)}",
                )
                self.assertGreater(len(views[key]), 0)

        self.assertGreater(
            float(views["sales_summary"]["total_order_value"].sum()), 0
        )
        self.assertTrue(views["review_summary"]["average_score"].between(0, 5).all())

    def test_derive_views_degrades_for_missing_inputs(self):
        views = derive_views({})

        self.assertEqual(set(views), set(VIEW_KEYS))
        for key in VIEW_KEYS:
            self.assertTrue(views[key].empty)


class TestSQLiteStore(LiveDataTestCase):
    def test_seed_creates_real_tables_and_sql_views(self):
        path = ensure_sqlite_store(self.db_path)

        self.assertTrue(path.exists())
        connection = sqlite3.connect(path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            views = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='view'"
                )
            }
        finally:
            # ``with sqlite3.connect(...)`` commits but never closes the handle,
            # which keeps the file locked on Windows.
            connection.close()

        self.assertTrue(set(VIEW_KEYS) <= tables)
        self.assertTrue(set(VIEW_SQL_NAMES.values()) <= views)

        stored = read_sqlite_views(path)
        for key in VIEW_KEYS:
            self.assertGreater(len(stored[key]), 0)

    def test_reset_restores_the_baseline(self):
        ensure_sqlite_store(self.db_path)
        baseline = read_sqlite_views(self.db_path)
        baseline_revenue = float(
            baseline["sales_summary"]["total_order_value"].sum()
        )

        updated, _ = simulate_orders(
            baseline, 40, now=pd.Timestamp("2026-11-03"), seed=3
        )
        sqlite_store.write_views(updated, path=self.db_path)
        self.assertGreater(
            float(
                read_sqlite_views(self.db_path)["sales_summary"][
                    "total_order_value"
                ].sum()
            ),
            baseline_revenue,
        )

        sqlite_store.reset_sqlite_store(self.db_path)
        restored = read_sqlite_views(self.db_path)
        self.assertAlmostEqual(
            float(restored["sales_summary"]["total_order_value"].sum()),
            baseline_revenue,
            places=2,
        )


class TestOrderSimulation(LiveDataTestCase):
    def test_simulation_grows_every_kpi_and_reaches_2026(self):
        ensure_sqlite_store(self.db_path)
        views = read_sqlite_views(self.db_path)

        before_revenue = float(views["sales_summary"]["total_order_value"].sum())
        before_orders = int(views["sales_summary"]["order_id"].nunique())
        before_customers = int(
            views["customer_segments"]["customer_unique_id"].nunique()
        )

        updated, stats = simulate_orders(
            views, 75, now=pd.Timestamp("2026-11-03"), seed=11
        )

        self.assertEqual(stats["orders_added"], 75)
        self.assertGreater(stats["revenue_added"], 0)
        self.assertGreater(stats["customers_added"], 0)
        self.assertEqual(
            int(updated["sales_summary"]["order_id"].nunique()),
            before_orders + 75,
        )
        self.assertGreater(
            float(updated["sales_summary"]["total_order_value"].sum()),
            before_revenue,
        )
        self.assertGreater(
            int(updated["customer_segments"]["customer_unique_id"].nunique()),
            before_customers,
        )

        dates = pd.to_datetime(
            updated["sales_summary"]["order_purchase_timestamp"], errors="coerce"
        )
        self.assertGreaterEqual(dates.max(), pd.Timestamp("2026-01-01"))
        self.assertLessEqual(dates.max(), pd.Timestamp("2026-11-03"))

    def test_dashboard_simulation_persists_to_sqlite(self):
        before = dashboard_database.load_data("SELECT * FROM vw_sales_summary;")
        before_revenue = float(before["total_order_value"].sum())
        before_orders = int(before["order_id"].nunique())

        stats = dashboard_database.simulate_new_orders(50)

        self.assertEqual(stats["target"], "sqlite")
        after = dashboard_database.load_data("SELECT * FROM vw_sales_summary;")
        self.assertGreater(float(after["total_order_value"].sum()), before_revenue)
        self.assertGreater(int(after["order_id"].nunique()), before_orders)
        self.assertEqual(
            dashboard_database.get_data_source_status()["mode"],
            dashboard_database.LIVE_SQLITE,
        )
        self.assertEqual(
            dashboard_database.get_source_label(),
            "LIVE - CLOUD SQL ENGINE",
        )


class TestUploadedCsv(LiveDataTestCase):
    def test_unified_orders_csv_derives_all_five_views(self):
        upload = pd.DataFrame(
            {
                "order_id": ["u1", "u2", "u3"],
                "order_date": ["2026-02-01", "2026-02-02", "2026-03-01"],
                "total_order_value": [100.0, 250.5, 75.25],
                "customer_unique_id": ["c1", "c2", "c1"],
                "customer_state": ["SP", "RJ", "SP"],
                "customer_city": ["sao paulo", "rio", "sao paulo"],
                "category_name": ["toys", "auto", "toys"],
                "payment_type": ["pix", "credit_card", "pix"],
                "review_score": [5, 3, 4],
            }
        )

        parsed, notes = views_from_dataframe(upload)

        self.assertEqual(set(parsed), set(VIEW_KEYS))
        self.assertEqual(len(parsed["sales_summary"]), 3)
        self.assertEqual(len(parsed["customer_segments"]), 2)
        self.assertTrue(notes)

    def test_applying_upload_overrides_every_dashboard_view(self):
        upload = pd.DataFrame(
            {
                "order_id": ["a1", "a2"],
                "order_date": ["2026-05-01", "2026-05-02"],
                "value": [500.0, 750.0],
                "customer_unique_id": ["ac1", "ac2"],
                "state": ["SP", "RJ"],
                "city": ["sao paulo", "rio"],
                "category": ["toys", "auto"],
                "payment_type": ["pix", "credit_card"],
                "review_score": [5, 4],
            }
        )

        summary = dashboard_database.apply_custom_views_from_frame(
            upload, source_name="unit_test.csv"
        )

        self.assertEqual(
            dashboard_database.get_data_source_status()["mode"],
            dashboard_database.SESSION_OVERRIDE,
        )
        self.assertEqual(
            dashboard_database.get_source_label(), "LIVE - CUSTOM DATA"
        )
        self.assertEqual(summary["total_rows"], 10)

        sales = dashboard_database.load_data("SELECT * FROM vw_sales_summary;")
        self.assertEqual(len(sales), 2)
        self.assertAlmostEqual(float(sales["total_order_value"].sum()), 1250.0)

        dashboard_database.clear_custom_views()
        self.assertFalse(dashboard_database.has_custom_views())

    def test_single_view_csv_keeps_other_views_live(self):
        baseline = dashboard_database.load_data(
            "SELECT * FROM vw_sales_summary;"
        )
        summary = dashboard_database.apply_custom_views_from_frame(
            baseline.head(3), view_key="sales_summary"
        )

        self.assertEqual(summary["views"], ["sales_summary"])
        sales = dashboard_database.load_data("SELECT * FROM vw_sales_summary;")
        self.assertEqual(len(sales), 3)

        # The other views stay populated from the live SQLite tier.
        payments = dashboard_database.load_data(
            "SELECT * FROM vw_payment_summary;"
        )
        self.assertGreater(len(payments), 0)


class TestEtlToDashboardSync(LiveDataTestCase):
    def _run_seed(self, seed: int, multiplier: float) -> dict:
        raw_dir = self.tmp / f"raw_{seed}"
        seed_info = seed_sample_raw_csvs(
            raw_dir=raw_dir,
            overwrite=True,
            seed=seed,
            order_multiplier=multiplier,
        )
        paths = {
            name: str(raw_dir / Path(path).name)
            for name, path in FILE_PATHS.items()
        }

        with patch.dict("etl.extract.FILE_PATHS", paths, clear=True), patch(
            "etl.pipeline.REPORTS_DIR", str(self.tmp / "reports")
        ), patch(
            "etl.load._load_to_mysql",
            side_effect=RuntimeError("mysql offline in tests"),
        ):
            result = run_pipeline(raise_on_error=False, load=True)

        return {"seed": seed_info, "result": result}

    def test_new_seed_etl_changes_sqlite_kpis(self):
        first = self._run_seed(seed=101, multiplier=1.0)
        self.assertEqual(first["result"]["status"], "success")
        self.assertEqual(first["result"]["load_target"], "sqlite")
        self.assertEqual(len(first["result"]["views_written"]), len(VIEW_KEYS))

        first_views = read_sqlite_views(self.db_path)
        first_revenue = float(
            first_views["sales_summary"]["total_order_value"].sum()
        )
        first_orders = int(first_views["sales_summary"]["order_id"].nunique())

        second = self._run_seed(seed=90210, multiplier=2.2)
        self.assertEqual(second["result"]["status"], "success")

        second_views = read_sqlite_views(self.db_path)
        second_revenue = float(
            second_views["sales_summary"]["total_order_value"].sum()
        )
        second_orders = int(second_views["sales_summary"]["order_id"].nunique())

        self.assertGreater(second_orders, first_orders)
        self.assertNotAlmostEqual(second_revenue, first_revenue, places=2)

        # The dashboard reads the freshly loaded SQLite data immediately.
        dashboard_database.reset_data_source()
        dashboard_sales = dashboard_database.load_data(
            "SELECT * FROM vw_sales_summary;"
        )
        self.assertEqual(len(dashboard_sales), second_orders)


if __name__ == "__main__":
    unittest.main()
