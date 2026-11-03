"""Payments tab: payment mix by count and volume."""

import pandas as pd
import streamlit as st

from dashboard.charts import ChartBuilder
from dashboard.theme import render_section_header

REQUIRED_COLUMNS = ("payment_type", "transaction_count", "total_volume")


def render_payment_dashboard(df: pd.DataFrame) -> None:
    render_section_header(
        "Payment Operations",
        "Transaction mix and processed volume by payment method.",
    )

    if df is None or df.empty:
        st.warning("No payment data available.")
        return

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        st.info(f"Payment data is missing required columns: {', '.join(missing)}.")
        return

    working = df.copy()
    for column in ("transaction_count", "total_volume"):
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0)

    # Demo data is monthly; the live view is already aggregated. Grouping both
    # by payment type keeps the charts stable for either shape.
    aggregated = (
        working.groupby("payment_type", as_index=False)[
            ["transaction_count", "total_volume"]
        ]
        .sum()
        .sort_values("total_volume", ascending=False)
    )
    aggregated["average_transaction_value"] = (
        aggregated["total_volume"] / aggregated["transaction_count"].replace(0, pd.NA)
    ).fillna(0)

    col1, col2 = st.columns(2)

    with col1:
        fig = ChartBuilder.create_pie_chart(
            aggregated,
            "payment_type",
            "transaction_count",
            "Payment Type Distribution (Count)",
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        fig2 = ChartBuilder.create_bar_chart(
            aggregated.sort_values("total_volume"),
            "payment_type",
            "total_volume",
            "Payment Volume by Type",
        )
        st.plotly_chart(fig2, width="stretch")
