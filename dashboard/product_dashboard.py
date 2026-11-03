"""Products tab: category revenue and units sold."""

import pandas as pd
import streamlit as st

from dashboard.charts import ChartBuilder
from dashboard.theme import render_section_header

REQUIRED_COLUMNS = ("category_name", "total_units_sold", "total_category_revenue")


def render_product_dashboard(df: pd.DataFrame) -> None:
    render_section_header(
        "Product Performance",
        "Category revenue leaders and their unit distribution.",
    )

    if df is None or df.empty:
        st.warning("No product data available.")
        return

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        st.info(f"Product data is missing required columns: {', '.join(missing)}.")
        return

    working = df.copy()
    for column in ("total_units_sold", "total_category_revenue"):
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0)

    aggregated = (
        working.groupby("category_name", as_index=False)[
            ["total_units_sold", "total_category_revenue"]
        ]
        .sum()
        .sort_values("total_category_revenue", ascending=False)
        .head(10)
    )

    col1, col2 = st.columns(2)

    with col1:
        fig = ChartBuilder.create_bar_chart(
            aggregated.sort_values("total_category_revenue"),
            "category_name",
            "total_category_revenue",
            "Top 10 Categories by Revenue",
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        fig2 = ChartBuilder.create_pie_chart(
            aggregated,
            "category_name",
            "total_units_sold",
            "Top 10 Categories by Units Sold",
        )
        st.plotly_chart(fig2, width="stretch")
