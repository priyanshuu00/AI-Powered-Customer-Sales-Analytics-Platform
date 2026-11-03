"""Unit tests for dashboard KPI helpers, dataframe filters, and prompt building."""

from __future__ import annotations

import unittest

import pandas as pd

from ai.prompt_builder import MAX_CHARS, MAX_ROWS, PromptBuilder
from dashboard.filters import apply_date_filter, apply_global_filters
from dashboard.kpi import (
    _numeric,
    _rating_label,
    _top_state,
    _weighted_average_rating,
)


class TestKPISanitisation(unittest.TestCase):
    def test_numeric_coerces_strings_and_drops_invalid_values(self):
        frame = pd.DataFrame({"value": ["10", 20.5, "n/a", None]})

        series = _numeric(frame, "value")

        self.assertEqual(list(series), [10.0, 20.5])

    def test_numeric_handles_missing_frames_and_columns(self):
        self.assertTrue(_numeric(None, "value").empty)
        self.assertTrue(_numeric(pd.DataFrame(), "value").empty)
        self.assertTrue(_numeric(pd.DataFrame({"other": [1]}), "value").empty)

    def test_weighted_average_rating_respects_review_counts(self):
        reviews = pd.DataFrame(
            {"average_score": [5.0, 1.0], "review_count": [9, 1]}
        )

        # (5 * 9 + 1 * 1) / 10
        self.assertAlmostEqual(_weighted_average_rating(reviews), 4.6, places=6)

    def test_weighted_average_rating_falls_back_to_plain_mean(self):
        reviews = pd.DataFrame({"average_score": [2.0, 4.0]})

        self.assertAlmostEqual(_weighted_average_rating(reviews), 3.0, places=6)

    def test_weighted_average_rating_handles_no_rows(self):
        self.assertEqual(_weighted_average_rating(pd.DataFrame()), 0.0)

    def test_rating_labels_cover_every_threshold(self):
        self.assertEqual(_rating_label(0), "No reviews yet")
        self.assertEqual(_rating_label(4.6), "Excellent")
        self.assertEqual(_rating_label(4.0), "Strong")
        self.assertEqual(_rating_label(3.5), "Healthy")
        self.assertEqual(_rating_label(3.0), "Mixed")
        self.assertEqual(_rating_label(2.9), "Needs attention")

    def test_top_state_returns_most_frequent_state(self):
        customers = pd.DataFrame(
            {"customer_state": ["SP", "SP", "SP", "RJ", "MG"]}
        )

        self.assertEqual(_top_state(customers), "SP")
        self.assertEqual(_top_state(pd.DataFrame()), "")


class TestDashboardFilters(unittest.TestCase):
    def setUp(self):
        self.sales = pd.DataFrame(
            {
                "order_purchase_timestamp": [
                    "2024-01-01 08:00",
                    "2024-01-31 22:30",
                    "2024-02-01 00:10",
                    "2024-03-15 12:00",
                ],
                "customer_state": ["SP", "RJ", "SP", "MG"],
                "customer_city": ["sao paulo", "rio de janeiro", "campinas", "belo"],
                "value": [10, 20, 30, 40],
            }
        )

    def test_date_filter_is_inclusive_and_ignores_time_of_day(self):
        filtered = apply_date_filter(
            self.sales, ("2024-01-01", "2024-01-31")
        )

        self.assertEqual(len(filtered), 2)
        self.assertEqual(list(filtered["value"]), [10, 20])

    def test_date_filter_returns_original_for_unsupported_input(self):
        self.assertIs(apply_date_filter(self.sales, None), self.sales)
        self.assertIs(apply_date_filter(self.sales, ("2024-01-01",)), self.sales)
        no_dates = pd.DataFrame({"value": [1, 2, 3]})
        self.assertIs(apply_date_filter(no_dates, ("2024-01-01", "2024-12-31")), no_dates)

    def test_date_filter_handles_unparseable_dates(self):
        frame = pd.DataFrame(
            {"order_purchase_timestamp": ["not-a-date", "also-bad"], "value": [1, 2]}
        )

        self.assertIs(
            apply_date_filter(frame, ("2024-01-01", "2024-12-31")), frame
        )

    def test_global_filters_apply_state_and_city(self):
        filtered = apply_global_filters(self.sales, {"state": ["SP"]})

        self.assertEqual(len(filtered), 2)
        self.assertTrue((filtered["customer_state"] == "SP").all())

        filtered_city = apply_global_filters(
            self.sales, {"state": ["SP"], "city": ["campinas"]}
        )
        self.assertEqual(list(filtered_city["customer_city"]), ["campinas"])

    def test_global_filters_ignore_unknown_columns(self):
        result = apply_global_filters(self.sales, {"category": ["toys"]})

        self.assertEqual(len(result), len(self.sales))


class TestPromptBuilder(unittest.TestCase):
    def test_nan_and_infinity_serialise_to_null(self):
        payload = {
            "revenue": float("nan"),
            "growth": float("inf"),
            "orders": 320,
        }

        text = PromptBuilder._serialise(payload)

        self.assertIn("null", text)
        self.assertIn('"orders": 320', text)
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)

    def test_dataframes_are_capped_at_max_rows(self):
        frame = pd.DataFrame({"value": range(MAX_ROWS * 3)})

        cleaned = PromptBuilder._clean(frame)

        self.assertEqual(len(cleaned), MAX_ROWS)

    def test_payloads_are_truncated_to_the_character_budget(self):
        text = PromptBuilder._serialise({"blob": "x" * (MAX_CHARS * 2)})

        self.assertEqual(len(text), MAX_CHARS)

    def test_chat_prompt_contains_question_and_context(self):
        prompt = PromptBuilder.build_chat_prompt(
            "Which categories lead?", {"kpis": {"revenue": 1234.5}}
        )

        self.assertIn("Which categories lead?", prompt)
        self.assertIn("1234.5", prompt)
        self.assertIn("AI Business Intelligence Assistant", prompt)

    def test_domain_prompts_embed_the_domain_label(self):
        prompt = PromptBuilder.build_insights_prompt(
            "Products", pd.DataFrame({"category": ["toys"]})
        )

        self.assertIn("Products", prompt)
        self.assertIn("Root Cause Analysis", prompt)


if __name__ == "__main__":
    unittest.main()
