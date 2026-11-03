"""Database-layer tests: demo view schema, determinism, and safe URL building."""

from __future__ import annotations

import unittest

import pandas as pd
from sqlalchemy.engine import Engine

from dashboard.database import generate_demo_views
from database.db_connection import DatabaseConnector, get_db_engine

EXPECTED_SCHEMA = {
    "sales_summary": {
        "order_id",
        "order_status",
        "order_purchase_timestamp",
        "customer_state",
        "customer_city",
        "total_order_value",
    },
    "customer_segments": {
        "customer_unique_id",
        "customer_city",
        "customer_state",
        "lifetime_orders",
        "lifetime_spent",
    },
    "product_performance": {
        "category_name",
        "total_units_sold",
        "total_category_revenue",
        "sale_month",
    },
    "payment_analysis": {
        "payment_type",
        "transaction_count",
        "total_volume",
        "average_transaction_value",
        "sale_month",
    },
    "review_summary": {
        "order_id",
        "average_score",
        "review_count",
        "review_creation_date",
    },
}


class TestDemoViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.views = generate_demo_views()

    def test_all_five_views_are_present(self):
        self.assertEqual(set(self.views), set(EXPECTED_SCHEMA))

    def test_every_view_matches_its_expected_schema(self):
        for name, expected_columns in EXPECTED_SCHEMA.items():
            with self.subTest(view=name):
                self.assertTrue(
                    expected_columns <= set(self.views[name].columns),
                    f"{name} is missing {expected_columns - set(self.views[name].columns)}",
                )

    def test_views_are_non_empty(self):
        for name, frame in self.views.items():
            with self.subTest(view=name):
                self.assertGreater(len(frame), 0)

    def test_identifier_columns_are_unique_where_expected(self):
        self.assertTrue(self.views["sales_summary"]["order_id"].is_unique)
        self.assertTrue(
            self.views["customer_segments"]["customer_unique_id"].is_unique
        )

    def test_date_columns_parse_cleanly(self):
        sales_dates = pd.to_datetime(
            self.views["sales_summary"]["order_purchase_timestamp"], errors="coerce"
        )
        review_dates = pd.to_datetime(
            self.views["review_summary"]["review_creation_date"], errors="coerce"
        )

        self.assertFalse(sales_dates.isna().any())
        self.assertFalse(review_dates.isna().any())

    def test_numeric_kpis_are_positive(self):
        sales = self.views["sales_summary"]
        self.assertGreater(float(sales["total_order_value"].sum()), 0)
        self.assertTrue((sales["total_order_value"] > 0).all())

        reviews = self.views["review_summary"]
        self.assertTrue(reviews["average_score"].between(1, 5).all())

    def test_generation_is_deterministic(self):
        again = generate_demo_views()

        for name in EXPECTED_SCHEMA:
            pd.testing.assert_frame_equal(self.views[name], again[name])

    def test_callers_receive_isolated_copies(self):
        first = generate_demo_views()
        first["sales_summary"].loc[:, "total_order_value"] = 0.0

        second = generate_demo_views()

        self.assertGreater(float(second["sales_summary"]["total_order_value"].sum()), 0)


class TestConnectionUrlSafety(unittest.TestCase):
    def test_special_characters_are_percent_encoded(self):
        connector = DatabaseConnector()
        connector.user = "analyst"
        connector.password = "p@ss:word/with@symbols"
        connector.host = "localhost"
        connector.port = 3306
        connector.database = "sales_analytics_db"

        rendered = connector.get_connection_url().render_as_string(
            hide_password=False
        )

        self.assertNotIn("p@ss", rendered)
        self.assertIn("p%40ss%3Aword%2Fwith%40symbols", rendered)
        self.assertTrue(rendered.startswith("mysql+mysqlconnector://analyst:"))

    def test_custom_port_and_database_are_preserved(self):
        connector = DatabaseConnector()
        connector.port = 3307
        connector.database = "analytics_test"

        url = connector.get_connection_url()

        self.assertEqual(url.port, 3307)
        self.assertEqual(url.database, "analytics_test")

    def test_invalid_port_env_falls_back_to_default(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {"DB_PORT": "not-a-number"}):
            connector = DatabaseConnector()

        self.assertEqual(connector.port, 3306)

    def test_get_db_engine_returns_a_sqlalchemy_engine_without_connecting(self):
        engine = get_db_engine()

        self.assertIsInstance(engine, Engine)
        self.assertIs(get_db_engine(), engine)


if __name__ == "__main__":
    unittest.main()
