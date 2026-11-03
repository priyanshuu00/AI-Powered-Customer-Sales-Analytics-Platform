"""Sales tab: monthly revenue trend and top states."""

import pandas as pd
import streamlit as st

from dashboard.charts import ChartBuilder
from dashboard.theme import render_section_header

REQUIRED_COLUMNS = ("order_purchase_timestamp", "total_order_value", "customer_state")


def render_sales_dashboard(df: pd.DataFrame) -> None:
    render_section_header(
        "Revenue Performance",
        "Monthly revenue trajectory and state-level contribution.",
    )

    if df is None or df.empty:
        st.warning("No sales data available.")
        return

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        st.info(f"Sales data is missing required columns: {', '.join(missing)}.")
        return

    working = df.copy()
    working["order_purchase_timestamp"] = pd.to_datetime(
        working["order_purchase_timestamp"], errors="coerce"
    )
    working["total_order_value"] = pd.to_numeric(
        working["total_order_value"], errors="coerce"
    )
    working = working.dropna(
        subset=["order_purchase_timestamp", "total_order_value"]
    )

    if working.empty:
        st.warning("No valid sales rows available for the selected filters.")
        return

    monthly = (
        working.groupby(working["order_purchase_timestamp"].dt.to_period("M"))[
            "total_order_value"
        ]
        .sum()
        .reset_index()
    )
    monthly["order_purchase_timestamp"] = monthly[
        "order_purchase_timestamp"
    ].astype(str)

    col1, col2 = st.columns(2)

    with col1:
        fig_line = ChartBuilder.create_line_chart(
            monthly,
            "order_purchase_timestamp",
            "total_order_value",
            "Revenue Trend (Monthly)",
        )
        st.plotly_chart(fig_line, width="stretch")

    with col2:
        states = (
            working.groupby("customer_state")["total_order_value"]
            .sum()
            .reset_index()
            .sort_values("total_order_value", ascending=False)
            .head(10)
            .sort_values("total_order_value")
        )
        fig_bar = ChartBuilder.create_bar_chart(
            states,
            "customer_state",
            "total_order_value",
            "Top 10 States by Revenue",
        )
        st.plotly_chart(fig_bar, width="stretch")
