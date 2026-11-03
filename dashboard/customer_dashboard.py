"""Customers tab: top cities and highest lifetime-value customers."""

import pandas as pd
import streamlit as st

from dashboard.charts import ChartBuilder
from dashboard.theme import render_section_header


def render_customer_dashboard(df: pd.DataFrame) -> None:
    render_section_header(
        "Customer Intelligence",
        "Geographic density and the customers driving lifetime value.",
    )

    if df is None or df.empty:
        st.warning("No customer data available.")
        return

    if "customer_city" not in df.columns or "customer_unique_id" not in df.columns:
        st.info("Customer data is missing city or identifier columns.")
        return

    col1, col2 = st.columns(2)

    with col1:
        counts = (
            df.groupby("customer_city")["customer_unique_id"]
            .nunique()
            .reset_index(name="customer_count")
            .sort_values("customer_count", ascending=False)
            .head(10)
            .sort_values("customer_count")
        )
        fig = ChartBuilder.create_bar_chart(
            counts,
            "customer_count",
            "customer_city",
            "Top 10 Cities by Customer Count",
            orientation="h",
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        if "lifetime_spent" not in df.columns:
            st.info("Customer data is missing lifetime value.")
            return

        top_customers = df.copy()
        top_customers["lifetime_spent"] = pd.to_numeric(
            top_customers["lifetime_spent"], errors="coerce"
        )
        top_customers = (
            top_customers.dropna(subset=["lifetime_spent"])
            .sort_values("lifetime_spent", ascending=False)
            .head(10)
        )
        top_customers["customer_unique_id_short"] = (
            top_customers["customer_unique_id"].astype(str).str[:8]
        )
        fig2 = ChartBuilder.create_bar_chart(
            top_customers,
            "customer_unique_id_short",
            "lifetime_spent",
            "Top 10 Customers by Lifetime Value",
        )
        st.plotly_chart(fig2, width="stretch")
