"""Streamlit dashboard application.

Runs both as the root entry point (``streamlit run app.py``) and directly
(``streamlit run dashboard/app.py``). Import paths are bootstrapped from this
file's location, so neither invocation depends on the caller's CWD.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Insert the dashboard folder first, then the repo root, so the root ends up
# with priority. This keeps ``dashboard/database.py`` from shadowing the
# top-level ``database`` package while still supporting bare sibling imports.
for _path in (PROJECT_ROOT / "dashboard", PROJECT_ROOT):
    _entry = str(_path)
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.database import (  # noqa: E402
    get_data_source_status,
    get_source_class,
    get_source_label,
    load_data,
)
from dashboard.filters import apply_date_filter  # noqa: E402
from dashboard.kpi import render_kpis  # noqa: E402
from dashboard.sidebar import render_sidebar  # noqa: E402
from dashboard.theme import apply_theme, render_divider  # noqa: E402
from dashboard.sales_dashboard import render_sales_dashboard  # noqa: E402
from dashboard.customer_dashboard import render_customer_dashboard  # noqa: E402
from dashboard.product_dashboard import render_product_dashboard  # noqa: E402
from dashboard.payment_dashboard import render_payment_dashboard  # noqa: E402
from dashboard.review_dashboard import render_review_dashboard  # noqa: E402
from dashboard.ai_dashboard import render_ai_dashboard  # noqa: E402
from dashboard.etl_dashboard import render_etl_dashboard  # noqa: E402
from dashboard.utils import get_csv_download_link  # noqa: E402

SALES_QUERY = "SELECT * FROM vw_sales_summary;"
CUSTOMERS_QUERY = "SELECT * FROM vw_customer_summary;"
CATEGORIES_QUERY = "SELECT * FROM vw_category_performance;"
PAYMENTS_QUERY = "SELECT * FROM vw_payment_summary;"
REVIEWS_QUERY = "SELECT * FROM vw_review_summary;"


def _apply_state_filter(df: pd.DataFrame, states: list) -> pd.DataFrame:
    if df is None or df.empty or not states:
        return df
    if "customer_state" not in df.columns:
        return df
    return df[df["customer_state"].isin(states)].copy()


def _format_date_range(date_range) -> str:
    if not date_range:
        return "All time"
    try:
        values = list(date_range)
        if len(values) != 2:
            return "All time"
        start = pd.to_datetime(values[0])
        end = pd.to_datetime(values[1])
        return f"{start:%b %d, %Y} to {end:%b %d, %Y}"
    except (TypeError, ValueError):
        return "All time"


def _render_hero(filters: dict) -> None:
    """Render the glassmorphic hero banner with status and filter pills."""

    status = get_data_source_status()
    mode = status.get("mode", "unknown")
    status_class = get_source_class(mode)
    status_label = get_source_label(mode)

    date_label = _format_date_range(filters.get("date_range"))
    states = filters.get("state") or []
    state_label = f"{len(states)} states selected" if states else "All states"

    st.markdown(
        f'<div class="hero-banner">'
        f'<div class="hero-top">'
        f'<div class="hero-copy">'
        f'<div class="hero-eyebrow">2026 Executive Intelligence</div>'
        f'<h1 class="hero-title">AI-Powered Customer Sales Analytics</h1>'
        f'<p class="hero-subtitle">Bento-grade visibility across revenue, customers, '
        f"products, payments, and satisfaction — engineered for fast executive "
        f"decision-making.</p>"
        f"</div>"
        f'<div class="hero-status">'
        f'<span class="status-pill {status_class}">'
        f'<span class="dot"></span>{html.escape(status_label)}</span>'
        f"</div>"
        f"</div>"
        f'<div class="hero-filters">'
        f'<span class="filter-label">Active filters</span>'
        f'<span class="filter-pill">{html.escape(date_label)}</span>'
        f'<span class="filter-pill">{html.escape(state_label)}</span>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def load_dashboard_data() -> dict:
    """Load all five dashboard views from the highest-priority tier."""

    return {
        "sales": load_data(SALES_QUERY),
        "customers": load_data(CUSTOMERS_QUERY),
        "categories": load_data(CATEGORIES_QUERY),
        "payments": load_data(PAYMENTS_QUERY),
        "reviews": load_data(REVIEWS_QUERY),
    }


def main() -> None:
    st.set_page_config(
        page_title="AI-Powered Sales Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_theme()

    frames = load_dashboard_data()
    df_sales = frames["sales"]
    df_customers = frames["customers"]
    df_categories = frames["categories"]
    df_payments = frames["payments"]
    df_reviews = frames["reviews"]

    filters = render_sidebar(df_sales)
    date_range = filters.get("date_range")
    states = filters.get("state") or []

    # Date filters are applied only to frames with a recognised date axis.
    df_sales = apply_date_filter(df_sales, date_range)
    df_customers = apply_date_filter(df_customers, date_range)
    df_categories = apply_date_filter(df_categories, date_range)
    df_payments = apply_date_filter(df_payments, date_range)
    df_reviews = apply_date_filter(df_reviews, date_range)

    df_sales = _apply_state_filter(df_sales, states)
    df_customers = _apply_state_filter(df_customers, states)

    # Keep the rating KPI aligned with the state-filtered sales population.
    if (
        states
        and df_sales is not None
        and not df_sales.empty
        and df_reviews is not None
        and not df_reviews.empty
        and "order_id" in df_sales.columns
        and "order_id" in df_reviews.columns
    ):
        df_reviews = df_reviews[
            df_reviews["order_id"].isin(df_sales["order_id"])
        ].copy()

    _render_hero(filters)
    render_kpis(df_sales, df_customers, df_reviews)

    render_divider()

    tab_sales, tab_customers, tab_products, tab_payments, tab_reviews, tab_ai, tab_etl = st.tabs(
        [
            "📈 Sales",
            "👥 Customers",
            "📦 Products",
            "💳 Payments",
            "⭐ Reviews",
            "✨ AI Copilot",
            "⚡ Data Studio & ETL",
        ]
    )

    with tab_sales:
        render_sales_dashboard(df_sales)
        if df_sales is not None and not df_sales.empty:
            st.markdown(
                get_csv_download_link(
                    df_sales, "sales_data.csv", "Export Sales CSV"
                ),
                unsafe_allow_html=True,
            )

    with tab_customers:
        render_customer_dashboard(df_customers)

    with tab_products:
        render_product_dashboard(df_categories)

    with tab_payments:
        render_payment_dashboard(df_payments)

    with tab_reviews:
        render_review_dashboard(df_reviews)

    with tab_ai:
        render_ai_dashboard(
            df_sales,
            df_customers,
            df_categories,
            df_payments,
            df_reviews,
        )

    with tab_etl:
        render_etl_dashboard(
            df_sales,
            df_customers,
            df_categories,
            df_payments,
            df_reviews,
        )


if __name__ == "__main__":
    main()
