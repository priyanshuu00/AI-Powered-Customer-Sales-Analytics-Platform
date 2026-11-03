"""Reviews tab: sentiment distribution from per-order review averages."""

import pandas as pd
import streamlit as st

from dashboard.charts import ChartBuilder
from dashboard.theme import render_section_header


def render_review_dashboard(df: pd.DataFrame) -> None:
    render_section_header(
        "Customer Sentiment",
        "Weighted satisfaction signals across reviewed orders.",
    )

    if df is None or df.empty:
        st.warning("No review data available.")
        return

    if "average_score" not in df.columns:
        st.info("Review data is missing the average_score column.")
        return

    scores = pd.to_numeric(df["average_score"], errors="coerce").dropna().clip(0, 5)
    if scores.empty:
        st.warning("No valid review scores available.")
        return

    buckets = pd.cut(
        scores,
        bins=[-0.01, 2.5, 3.5, 5.0],
        labels=["Negative", "Neutral", "Positive"],
        include_lowest=True,
    )
    distribution = (
        buckets.value_counts()
        .rename_axis("Sentiment")
        .reset_index(name="Count")
        .sort_values("Sentiment")
    )
    distribution = distribution[distribution["Count"] > 0]

    fig = ChartBuilder.create_pie_chart(
        distribution,
        "Sentiment",
        "Count",
        "Review Sentiment Distribution",
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Based on {len(scores):,} reviewed orders.")
