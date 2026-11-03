"""AI report composition and chat interface.

``AIReportGenerator`` no longer ships hardcoded demo numbers. It accepts real
dicts/DataFrames from the dashboard (or loads the deterministic demo views when
run as a CLI), composes a Markdown report, saves it as UTF-8 inside ``reports/``,
and returns the report text so callers can render or download it directly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .ai_logger import setup_logger
from .executive_summary import ExecutiveSummaryGenerator
from .gemini_client import GeminiClient
from .insight_generator import InsightGenerator
from .prompt_builder import PromptBuilder
from .recommendation_engine import RecommendationEngine

logger = setup_logger("ReportGenerator")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_REPORT_NAME = "ai_business_report.md"

SECTION_KEYS = (
    "executive_summary",
    "sales_insights",
    "customer_insights",
    "product_insights",
    "payment_insights",
    "review_insights",
    "recommendations",
)


class ChatInterface:
    """Small wrapper around the Gemini client used by the copilot tab."""

    def __init__(self, client: GeminiClient, context: Optional[dict] = None):
        self.client = client
        self.context = context or {}

    def answer(self, question: str) -> Optional[str]:
        """Return the model answer, or ``None`` so callers can fall back."""

        if not question or not str(question).strip():
            return None
        prompt = PromptBuilder.build_chat_prompt(question, self.context)
        return self.client.generate_response(prompt)

    def ask(self, question: str) -> str:
        """Backward-compatible string answer with a safe generic fallback."""

        response = self.answer(question)
        if response:
            return response
        return "I'm sorry, I could not process that request."


class AIReportGenerator:
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
        self.exec_summary_gen = ExecutiveSummaryGenerator(self.client)
        self.insight_gen = InsightGenerator(self.client)
        self.rec_gen = RecommendationEngine(self.client)
        self.last_report: Optional[str] = None
        self.last_report_path: Optional[Path] = None

    # ------------------------------------------------------------------ #
    # Section generation
    # ------------------------------------------------------------------ #

    def _generate_sections(
        self,
        kpis: Any,
        sales_data: Any,
        customer_data: Any,
        product_data: Any = None,
        payment_data: Any = None,
        review_data: Any = None,
    ) -> Dict[str, str]:
        logger.info("Generating AI report sections...")

        sales_insights = self.insight_gen.generate("Sales", sales_data)
        customer_insights = self.insight_gen.generate("Customers", customer_data)

        combined = (
            f"Sales Insights:\n{sales_insights}\n\n"
            f"Customer Insights:\n{customer_insights}"
        )
        if product_data is not None:
            combined += f"\n\nProduct Insights:\n{self.insight_gen.generate('Products', product_data)}"
        if payment_data is not None:
            combined += f"\n\nPayment Insights:\n{self.insight_gen.generate('Payments', payment_data)}"
        if review_data is not None:
            combined += f"\n\nReview Insights:\n{self.insight_gen.generate('Reviews', review_data)}"

        return {
            "executive_summary": self.exec_summary_gen.generate(kpis),
            "sales_insights": sales_insights,
            "customer_insights": customer_insights,
            "product_insights": (
                self.insight_gen.generate("Products", product_data)
                if product_data is not None
                else ""
            ),
            "payment_insights": (
                self.insight_gen.generate("Payments", payment_data)
                if payment_data is not None
                else ""
            ),
            "review_insights": (
                self.insight_gen.generate("Reviews", review_data)
                if review_data is not None
                else ""
            ),
            "recommendations": self.rec_gen.generate(combined),
        }

    # ------------------------------------------------------------------ #
    # Composition and persistence
    # ------------------------------------------------------------------ #

    @staticmethod
    def render_report(
        sections: Mapping[str, str],
        meta: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Compose Markdown from already-generated sections."""

        meta = dict(meta or {})
        generated = meta.get("generated_at") or datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
        data_mode = str(meta.get("data_source") or "dashboard data")
        engine = str(meta.get("engine") or "AI Business Intelligence Engine")

        def block(key: str) -> str:
            text = str(sections.get(key) or "").strip()
            return text if text else "_No content generated for this section._"

        insight_blocks = [
            ("Sales", block("sales_insights")),
            ("Customers", block("customer_insights")),
            ("Products", block("product_insights")),
            ("Payments", block("payment_insights")),
            ("Reviews", block("review_insights")),
        ]
        insight_markdown = "\n\n".join(
            f"### {name}\n{text}" for name, text in insight_blocks if text
        )

        return f"""# AI Business Intelligence Report

_Generated {generated} · Data source: {data_mode} · Engine: {engine}_

## Executive Summary
{block("executive_summary")}

## Business Insights & Root Cause Analysis
{insight_markdown}

## Recommendations
{block("recommendations")}

## Conclusion
This report was generated from the currently filtered dashboard datasets.
Validate the recommendations with departmental owners before committing budget
or inventory changes.
"""

    def _save(self, content: str, filename: str) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / Path(filename or DEFAULT_REPORT_NAME).name
        path.write_text(content, encoding="utf-8")
        logger.info("Report generated successfully at %s", path)
        return path

    def generate_full_report(
        self,
        kpis: Any,
        sales_data: Any,
        customer_data: Any,
        product_data: Any = None,
        payment_data: Any = None,
        review_data: Any = None,
        sections: Optional[Mapping[str, str]] = None,
        filename: str = DEFAULT_REPORT_NAME,
        save: bool = True,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Build (and optionally save) the full report, returning its Markdown.

        ``sections`` lets the caller inject pre-computed (for example, locally
        generated fallback) text so a report never embeds "AI unavailable"
        placeholders.
        """

        provided = {key: str(value) for key, value in (sections or {}).items()}
        if not all(provided.get(key, "").strip() for key in SECTION_KEYS):
            generated = self._generate_sections(
                kpis,
                sales_data,
                customer_data,
                product_data=product_data,
                payment_data=payment_data,
                review_data=review_data,
            )
            for key, value in generated.items():
                provided.setdefault(key, value)
                if not provided[key].strip():
                    provided[key] = value

        content = self.render_report(provided, meta=meta)
        self.last_report = content

        if save:
            try:
                self.last_report_path = self._save(content, filename)
            except OSError as exc:  # pragma: no cover - filesystem failures
                logger.error("Could not save report: %s", exc)
                self.last_report_path = None

        return content


def _load_demo_payloads() -> tuple[dict, dict, dict, dict, dict, dict]:
    """Build real payloads from deterministic demo views for CLI usage."""

    from dashboard.database import generate_demo_views

    frames = generate_demo_views()
    sales = frames["sales_summary"]
    customers = frames["customer_segments"]
    products = frames["product_performance"]
    payments = frames["payment_analysis"]
    reviews = frames["review_summary"]

    kpis = {
        "total_revenue": round(float(sales["total_order_value"].sum()), 2),
        "total_orders": int(sales["order_id"].nunique()),
        "total_customers": int(customers["customer_unique_id"].nunique()),
        "average_rating": round(float(reviews["average_score"].mean()), 2),
    }
    return kpis, sales, customers, products, payments, reviews


if __name__ == "__main__":
    try:
        kpis, sales, customers, products, payments, reviews = _load_demo_payloads()
        generator = AIReportGenerator()
        generator.generate_full_report(
            kpis,
            sales,
            customers,
            product_data=products,
            payment_data=payments,
            review_data=reviews,
            meta={"data_source": "deterministic demo views", "engine": "CLI"},
        )
        print(f"Report written to {generator.last_report_path}")
    except Exception as exc:  # pragma: no cover - CLI convenience
        logger.error("Process failed: %s", exc)
