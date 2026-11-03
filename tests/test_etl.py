"""ETL tests: sample data, validation, transformation, and pipeline contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from etl.config import FILE_PATHS
from etl.pipeline import run_pipeline
from etl.sample_data import build_sample_frames, seed_sample_raw_csvs
from etl.transform import Transform, transform_data
from etl.validator import (
    check_duplicate_rows,
    check_missing_values,
    validate_data,
)

EXPECTED_TABLES = {
    "geolocation",
    "customers",
    "sellers",
    "products",
    "category_translation",
    "orders",
    "order_items",
    "payments",
    "reviews",
}


class TestSampleData(unittest.TestCase):
    def test_build_sample_frames_covers_every_expected_table(self):
        frames = build_sample_frames()

        self.assertEqual(set(frames), EXPECTED_TABLES)
        self.assertEqual(set(frames), set(FILE_PATHS))
        for name, frame in frames.items():
            self.assertFalse(frame.empty, f"{name} sample frame is empty")

    def test_sample_frames_are_deterministic(self):
        first = build_sample_frames()
        second = build_sample_frames()

        for name in first:
            pd.testing.assert_frame_equal(first[name], second[name])

    def test_sample_frames_keep_referential_integrity(self):
        frames = build_sample_frames()

        order_ids = set(frames["orders"]["order_id"])
        customer_ids = set(frames["customers"]["customer_id"])
        product_ids = set(frames["products"]["product_id"])
        seller_ids = set(frames["sellers"]["seller_id"])

        self.assertTrue(set(frames["orders"]["customer_id"]) <= customer_ids)
        self.assertTrue(set(frames["order_items"]["order_id"]) <= order_ids)
        self.assertTrue(set(frames["order_items"]["product_id"]) <= product_ids)
        self.assertTrue(set(frames["order_items"]["seller_id"]) <= seller_ids)
        self.assertTrue(set(frames["payments"]["order_id"]) <= order_ids)
        self.assertTrue(set(frames["reviews"]["order_id"]) <= order_ids)

    def test_seed_writes_missing_files_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp)

            first = seed_sample_raw_csvs(raw_dir=raw_dir)
            self.assertEqual(first["total_files"], len(EXPECTED_TABLES))
            self.assertEqual(len(first["created"]), len(EXPECTED_TABLES))
            self.assertEqual(first["skipped"], [])
            for filename in first["created"]:
                self.assertTrue((raw_dir / filename).exists())

            sentinel = raw_dir / "olist_orders_dataset.csv"
            sentinel.write_text("order_id\nsentinel\n", encoding="utf-8")

            second = seed_sample_raw_csvs(raw_dir=raw_dir)
            self.assertEqual(second["created"], [])
            self.assertEqual(len(second["skipped"]), len(EXPECTED_TABLES))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "order_id\nsentinel\n")


class TestValidator(unittest.TestCase):
    def test_duplicate_rows_are_counted(self):
        frame = pd.DataFrame({"order_id": ["1", "1", "2"], "value": [10, 10, 20]})

        self.assertEqual(check_duplicate_rows(frame, "orders"), 1)

    def test_missing_values_are_grouped_by_column(self):
        frame = pd.DataFrame({"a": [1, None], "b": [None, None]})

        self.assertEqual(check_missing_values(frame, "t"), {"a": 1, "b": 2})

    def test_validate_data_reports_duplicates_missing_and_null_pks(self):
        frame = pd.DataFrame(
            {
                "order_id": ["1", "1", None],
                "value": [10, 10, None],
            }
        )

        stats = validate_data({"orders": frame})["orders"]

        self.assertEqual(stats["total_rows"], 3)
        self.assertEqual(stats["duplicate_rows"], 1)
        self.assertEqual(stats["null_pks"], 1)
        self.assertEqual(stats["missing_values"]["value"], 1)

    def test_validate_data_skips_pk_check_for_unknown_tables(self):
        stats = validate_data({"custom_table": pd.DataFrame({"x": [1, 2]})})

        self.assertEqual(stats["custom_table"]["null_pks"], 0)


class TestTransform(unittest.TestCase):
    def setUp(self):
        self.raw_data = pd.DataFrame(
            {"id": [1, 2, 2, 3], "name": ["A", "B", "B", "C"]}
        )
        self.transformer = Transform()

    def test_remove_duplicates(self):
        cleaned = self.transformer.clean_data({"test": self.raw_data})["test"]

        self.assertEqual(len(cleaned), 3)

    def test_transform_data_fills_review_comments_and_parses_dates(self):
        dfs = {
            "orders": pd.DataFrame(
                {
                    "order_id": ["o1"],
                    "customer_id": ["c1"],
                    "order_purchase_timestamp": ["2024-01-01 10:00:00"],
                }
            ),
            "reviews": pd.DataFrame(
                {
                    "review_id": ["r1"],
                    "order_id": ["o1"],
                    "review_comment_title": [None],
                    "review_comment_message": [None],
                    "review_creation_date": ["2024-01-05"],
                }
            ),
        }

        cleaned = transform_data(dfs)

        self.assertEqual(cleaned["reviews"]["review_comment_title"].iloc[0], "")
        self.assertTrue(
            pd.api.types.is_datetime64_any_dtype(
                cleaned["orders"]["order_purchase_timestamp"]
            )
        )

    def test_transform_data_drops_orphaned_order_items(self):
        dfs = {
            "orders": pd.DataFrame({"order_id": ["o1"], "customer_id": ["c1"]}),
            "order_items": pd.DataFrame(
                {
                    "order_id": ["o1", "orphan"],
                    "product_id": ["p1", "p1"],
                    "seller_id": ["s1", "s1"],
                }
            ),
        }

        cleaned = transform_data(dfs)

        self.assertEqual(list(cleaned["order_items"]["order_id"]), ["o1"])


class TestPipelineContract(unittest.TestCase):
    def _seed_and_patch(self, raw_dir: Path):
        """Seed real CSVs into a temp vault and repoint the extractor at it."""

        seed_sample_raw_csvs(raw_dir=raw_dir)
        return {
            name: str(raw_dir / Path(path).name)
            for name, path in FILE_PATHS.items()
        }

    def test_run_pipeline_without_load_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = self._seed_and_patch(tmp_path / "raw")

            with patch.dict("etl.extract.FILE_PATHS", paths, clear=True), patch(
                "etl.pipeline.REPORTS_DIR", str(tmp_path / "reports")
            ):
                result = run_pipeline(load=False)

            self.assertEqual(result["status"], "success")
            self.assertIsNone(result["error"])
            self.assertGreater(result["rows_extracted"], 0)
            self.assertGreater(result["rows_transformed"], 0)
            self.assertEqual(result["rows_processed"], result["rows_transformed"])
            self.assertEqual(result["rows_loaded"], 0)
            self.assertGreaterEqual(result["execution_time"], 0)

            stage_names = [stage["name"] for stage in result["stages"]]
            self.assertEqual(
                stage_names,
                ["Extract", "Validate", "Transform", "Load", "Report"],
            )
            load_stage = next(s for s in result["stages"] if s["name"] == "Load")
            self.assertEqual(load_stage["status"], "skipped")

            report_path = Path(result["report_path"])
            self.assertTrue(report_path.exists())
            self.assertIn("ETL SUMMARY REPORT", report_path.read_text(encoding="utf-8"))

    def test_run_pipeline_reports_extract_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "etl.pipeline.extract_data",
                side_effect=RuntimeError("vault is empty"),
            ), patch("etl.pipeline.REPORTS_DIR", str(Path(tmp) / "reports")):
                result = run_pipeline(load=False)

        self.assertEqual(result["status"], "error")
        self.assertIn("vault is empty", result["error"])
        self.assertEqual(result["stages"][0]["status"], "error")

    def test_run_pipeline_raises_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "etl.pipeline.extract_data",
                side_effect=RuntimeError("boom"),
            ), patch("etl.pipeline.REPORTS_DIR", str(Path(tmp) / "reports")):
                with self.assertRaises(RuntimeError):
                    run_pipeline(load=False, raise_on_error=True)


if __name__ == "__main__":
    unittest.main()
