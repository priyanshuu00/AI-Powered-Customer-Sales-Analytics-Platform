"""Integration tests: AI report composition, deterministic analyst, and the UI."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import dashboard.database as dashboard_database
from ai.gemini_client import GeminiClient
from ai.report_generator import AIReportGenerator
from dashboard import local_analyst
from dashboard.database import generate_demo_views
from etl import sqlite_store

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_TABS = [
    "📈 Sales",
    "👥 Customers",
    "📦 Products",
    "💳 Payments",
    "⭐ Reviews",
    "✨ AI Copilot",
    "⚡ Data Studio & ETL",
]

SECTION_KEYS = (
    "executive_summary",
    "sales_insights",
    "customer_insights",
    "product_insights",
    "payment_insights",
    "review_insights",
    "recommendations",
)


class OfflineGeminiClient:
    """Stands in for Gemini when the quota/network is unavailable."""

    model_name = "offline-stub"
    is_configured = False
    is_ready = False
    transport = "https"
    last_error = "simulated outage"

    def generate_response(self, prompt, use_cache=True):
        return None

    def unavailable_message(self, feature: str) -> str:
        return f"AI {feature} unavailable: simulated outage."


def demo_payloads():
    frames = generate_demo_views()
    return (
        frames["sales_summary"],
        frames["customer_segments"],
        frames["product_performance"],
        frames["payment_analysis"],
        frames["review_summary"],
    )


def demo_metrics():
    return local_analyst.compute_metrics(*demo_payloads())


def build_sections(metrics):
    return {
        "executive_summary": local_analyst.executive_summary(metrics),
        "sales_insights": local_analyst.sales_insights(metrics),
        "customer_insights": local_analyst.customer_insights(metrics),
        "product_insights": local_analyst.product_insights(metrics),
        "payment_insights": local_analyst.payment_insights(metrics),
        "review_insights": local_analyst.review_insights(metrics),
        "recommendations": local_analyst.recommendations(metrics),
    }


class TestReportGenerator(unittest.TestCase):
    def test_full_report_uses_injected_sections_and_saves_utf8(self):
        metrics = demo_metrics()
        sections = build_sections(metrics)
        sales, customers, products, payments, reviews = demo_payloads()

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with patch("ai.report_generator.REPORTS_DIR", target):
                generator = AIReportGenerator(client=OfflineGeminiClient())
                report = generator.generate_full_report(
                    metrics,
                    sales,
                    customers,
                    product_data=products,
                    payment_data=payments,
                    review_data=reviews,
                    sections=sections,
                    filename="executive_ai_report.md",
                    meta={"data_source": "unit-test demo", "engine": "offline"},
                )

            self.assertIsInstance(report, str)
            self.assertIn("# AI Business Intelligence Report", report)
            self.assertIn("## Executive Summary", report)
            self.assertIn("## Recommendations", report)
            self.assertNotIn("AI unavailable", report)

            saved = target / "executive_ai_report.md"
            self.assertTrue(saved.exists())
            self.assertEqual(saved.read_text(encoding="utf-8"), report)
            self.assertEqual(generator.last_report_path, saved)

    def test_full_report_generates_sections_when_none_injected(self):
        metrics = demo_metrics()
        sales, customers, products, payments, reviews = demo_payloads()

        with tempfile.TemporaryDirectory() as tmp:
            with patch("ai.report_generator.REPORTS_DIR", Path(tmp)):
                report = AIReportGenerator(
                    client=OfflineGeminiClient()
                ).generate_full_report(
                    metrics,
                    sales,
                    customers,
                    product_data=products,
                    payment_data=payments,
                    review_data=reviews,
                    filename="generated.md",
                )

        for heading in (
            "## Executive Summary",
            "### Sales",
            "### Customers",
            "### Products",
            "### Payments",
            "### Reviews",
            "## Recommendations",
        ):
            self.assertIn(heading, report)

    def test_report_can_skip_disk_persistence(self):
        metrics = demo_metrics()
        sales, customers, _, _, _ = demo_payloads()

        generator = AIReportGenerator(client=OfflineGeminiClient())
        report = generator.generate_full_report(
            metrics,
            sales,
            customers,
            sections=build_sections(metrics),
            save=False,
        )

        self.assertIsNone(generator.last_report_path)
        self.assertIn("Recommendations", report)

    def test_render_report_marks_empty_sections(self):
        text = AIReportGenerator.render_report({})

        self.assertIn("_No content generated for this section._", text)


class TestLocalAnalyst(unittest.TestCase):
    def test_metrics_are_derived_from_the_frames(self):
        metrics = demo_metrics()

        self.assertGreater(metrics["revenue"], 0)
        self.assertEqual(metrics["orders"], 320)
        self.assertGreater(metrics["unique_customers"], 0)
        self.assertTrue(0 < metrics["rating"] <= 5)
        self.assertTrue(0 <= metrics["repeat_ratio"] <= 1)
        self.assertEqual(metrics["rows"]["sales"], 320)

    def test_business_health_is_bounded(self):
        score, label = local_analyst.business_health(demo_metrics())

        self.assertGreaterEqual(score, 5)
        self.assertLessEqual(score, 99)
        self.assertIn(
            label, {"Excellent", "Strong", "Healthy", "Watch list", "At risk"}
        )

    def test_every_section_produces_text(self):
        metrics = demo_metrics()

        for section in build_sections(metrics).values():
            self.assertTrue(section.strip())

    def test_chat_routes_questions_to_the_right_domain(self):
        metrics = demo_metrics()

        cases = {
            "Which product categories drive revenue?": "Category performance",
            "Summarize customer satisfaction and review risks": "Satisfaction",
            "Where should we focus marketing by state?": "Where to focus next",
            "What is our payment mix?": "Payment mix",
            "How is customer retention?": "Customer base",
            "What is the revenue trend?": "Sales performance",
        }
        for question, marker in cases.items():
            with self.subTest(question=question):
                answer = local_analyst.answer_question(question, metrics)
                self.assertIn(marker, answer)

    def test_unknown_question_falls_back_to_executive_snapshot(self):
        answer = local_analyst.answer_question("Tell me a joke", demo_metrics())

        self.assertIn("Closest available analysis", answer)

    def test_empty_frames_degrade_without_raising(self):
        metrics = local_analyst.compute_metrics(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        )

        self.assertEqual(metrics["revenue"], 0.0)
        self.assertIn("No sales rows", local_analyst.sales_insights(metrics))
        self.assertTrue(local_analyst.recommendations(metrics))


class TestGeminiClientDegradation(unittest.TestCase):
    def test_missing_key_returns_none_and_explains(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            client = GeminiClient()

        self.assertFalse(client.is_configured)
        self.assertFalse(client.is_ready)
        self.assertIsNone(client.generate_response("hello"))
        self.assertIn("GEMINI_API_KEY", client.unavailable_message("summary"))
        self.assertIn("https", client.transport)

    def test_blank_prompt_is_rejected(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key-for-validation"}):
            client = GeminiClient()
        # The blank-prompt guard runs before any transport is selected.
        client._https_only = True

        with self.assertRaises(ValueError):
            client.generate_response("   ")


class TestStreamlitApp(unittest.TestCase):
    """Drives the real app against an isolated SQLite store and offline MySQL."""

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
        dashboard_database.reset_data_source()
        sqlite_store.dispose_sqlite_engines(self.db_path)
        self._probe.stop()
        self._env.stop()
        self._tmp.cleanup()

    def _app(self):
        from streamlit.testing.v1 import AppTest

        return AppTest.from_file(
            str(PROJECT_ROOT / "app.py"), default_timeout=240
        )

    @staticmethod
    def _markdown_text(app) -> str:
        """Concatenate every markdown element, including the sidebar."""

        chunks = [str(element.value) for element in app.markdown]
        try:
            chunks.extend(str(element.value) for element in app.sidebar.markdown)
        except Exception:  # pragma: no cover - older AppTest API
            pass
        return "\n".join(chunks)

    @classmethod
    def _kpi_number(cls, app, label: str) -> float:
        """Read a KPI card value from the rendered bento-grid markdown."""

        markup = cls._markdown_text(app)
        pattern = (
            r'kpi-label">' + re.escape(label) + r"</div>.*?"
            r'kpi-value">\$?([\d,]+(?:\.\d+)?)'
        )
        match = re.search(pattern, markup, re.S)
        if match is None:
            raise AssertionError(f"KPI card not found for {label!r}")
        return float(match.group(1).replace(",", ""))

    def test_all_seven_tabs_render_without_errors(self):
        app = self._app()
        with patch.object(GeminiClient, "generate_response", return_value=None):
            app.run()

        self.assertEqual([error.value for error in app.error], [])
        self.assertEqual([str(exc.value) for exc in app.exception], [])
        self.assertEqual([tab.label for tab in app.tabs], EXPECTED_TABS)
        self.assertEqual(
            app.session_state["_data_source_status"]["mode"],
            dashboard_database.LIVE_SQLITE,
        )
        self.assertIn("LIVE - CLOUD SQL ENGINE", self._markdown_text(app))

        button_labels = {button.label for button in app.button}
        self.assertIn("Generate Executive Summary", button_labels)
        self.assertIn("Generate Full Executive Report", button_labels)
        self.assertIn("Seed Sample Raw CSVs & Run ETL Pipeline", button_labels)
        self.assertIn("➕ Simulate New Orders", button_labels)
        self.assertIn("🔄 Reset to Baseline Dataset", button_labels)
        self.assertIn("Apply Uploaded CSV to Live Dashboard", button_labels)

    def test_ai_action_survives_an_offline_model(self):
        app = self._app()
        with patch.object(GeminiClient, "generate_response", return_value=None):
            app.run()
            for button in app.button:
                if button.key == "ai_exec_button":
                    button.click()
                    break
            else:  # pragma: no cover - widget disappeared
                self.fail("ai_exec_button not found")
            app.run()

        self.assertEqual([str(exc.value) for exc in app.exception], [])
        self.assertEqual([error.value for error in app.error], [])
        results = app.session_state["ai_results"]
        self.assertIn("executive", results)
        self.assertEqual(results["executive"]["source"], "fallback")
        self.assertTrue(results["executive"]["text"].strip())

    def test_simulated_orders_increase_revenue_and_orders(self):
        app = self._app()
        with patch.object(GeminiClient, "generate_response", return_value=None):
            app.run()

            revenue_before = self._kpi_number(app, "Total Revenue")
            orders_before = self._kpi_number(app, "Total Orders")
            self.assertGreater(revenue_before, 0)
            self.assertGreater(orders_before, 0)

            clicked = False
            for button in app.button:
                if button.key == "simulate_orders_button":
                    button.click()
                    clicked = True
                    break
            self.assertTrue(clicked, "simulate_orders_button not found")
            app.run()

            self.assertEqual([str(exc.value) for exc in app.exception], [])
            self.assertEqual([error.value for error in app.error], [])

            revenue_after = self._kpi_number(app, "Total Revenue")
            orders_after = self._kpi_number(app, "Total Orders")

        self.assertGreater(revenue_after, revenue_before)
        self.assertGreater(orders_after, orders_before)
        self.assertEqual(
            app.session_state["_data_source_status"]["mode"],
            dashboard_database.LIVE_SQLITE,
        )
        self.assertIn("LIVE - CLOUD SQL ENGINE", self._markdown_text(app))

    def test_uploaded_csv_drives_every_dashboard_tab(self):
        upload = pd.DataFrame(
            {
                "order_id": ["up-1", "up-2", "up-3"],
                "order_date": ["2026-04-01", "2026-04-02", "2026-04-03"],
                "value": [400.0, 350.0, 250.0],
                "customer_unique_id": ["cust-a", "cust-b", "cust-a"],
                "state": ["SP", "RJ", "SP"],
                "city": ["sao paulo", "rio de janeiro", "sao paulo"],
                "category": ["toys", "auto", "toys"],
                "payment_type": ["pix", "credit_card", "pix"],
                "review_score": [5, 4, 5],
            }
        )
        views, notes = sqlite_store.views_from_dataframe(upload)
        self.assertTrue(notes)

        app = self._app()
        app.session_state["custom_views"] = views
        app.session_state["_data_source_status"] = {
            "mode": dashboard_database.SESSION_OVERRIDE,
            "message": "Uploaded CSV is driving the dashboard.",
            "since": 0.0,
            "detail": None,
        }
        with patch.object(GeminiClient, "generate_response", return_value=None):
            app.run()

        self.assertEqual([str(exc.value) for exc in app.exception], [])
        self.assertEqual([error.value for error in app.error], [])
        self.assertIn("LIVE - CUSTOM DATA", self._markdown_text(app))
        self.assertAlmostEqual(
            self._kpi_number(app, "Total Revenue"), 1000.0, places=2
        )
        self.assertAlmostEqual(self._kpi_number(app, "Total Orders"), 3.0)
        self.assertAlmostEqual(
            self._kpi_number(app, "Unique Customers"), 2.0
        )

    def test_baseline_reset_restores_the_seeded_dataset(self):
        app = self._app()
        with patch.object(GeminiClient, "generate_response", return_value=None):
            app.run()
            baseline_revenue = self._kpi_number(app, "Total Revenue")

            for button in app.button:
                if button.key == "simulate_orders_button":
                    button.click()
                    break
            app.run()
            self.assertGreater(
                self._kpi_number(app, "Total Revenue"), baseline_revenue
            )

            for button in app.button:
                if button.key == "reset_baseline_button":
                    button.click()
                    break
            app.run()

            self.assertEqual([str(exc.value) for exc in app.exception], [])
            self.assertAlmostEqual(
                self._kpi_number(app, "Total Revenue"),
                baseline_revenue,
                places=2,
            )
        self.assertFalse(dashboard_database.has_custom_views())


if __name__ == "__main__":
    unittest.main()
