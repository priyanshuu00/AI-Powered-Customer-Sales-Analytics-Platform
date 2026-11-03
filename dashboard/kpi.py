"""Bento-grid executive KPI cards.

The public ``render_kpis`` signature is unchanged, so ``dashboard/app.py``
continues to call it with ``(sales_df, customers_df, reviews_df)``.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from dashboard.theme import render_section_header


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _weighted_average_rating(reviews_df: pd.DataFrame) -> float:
    scores = _numeric(reviews_df, "average_score")
    if scores.empty:
        return 0.0

    if "review_count" in reviews_df.columns:
        counts = pd.to_numeric(reviews_df["review_count"], errors="coerce")
        valid = scores.index.intersection(counts.dropna().index)
        if len(valid):
            weights = counts.loc[valid].clip(lower=1)
            total_weight = weights.sum()
            if total_weight > 0:
                return float((scores.loc[valid] * weights).sum() / total_weight)

    return float(scores.mean())


def _rating_label(rating: float) -> str:
    if rating <= 0:
        return "No reviews yet"
    if rating >= 4.5:
        return "Excellent"
    if rating >= 4.0:
        return "Strong"
    if rating >= 3.5:
        return "Healthy"
    if rating >= 3.0:
        return "Mixed"
    return "Needs attention"


def _rating_stars(rating: float) -> str:
    filled = max(0, min(5, int(round(rating))))
    return "★" * filled + "☆" * (5 - filled)


def _top_state(customers_df: pd.DataFrame) -> str:
    if (
        customers_df is None
        or customers_df.empty
        or "customer_state" not in customers_df.columns
    ):
        return ""
    counts = customers_df["customer_state"].dropna().value_counts()
    return str(counts.index[0]) if not counts.empty else ""


def _bento_card(
    accent: str,
    label: str,
    value: str,
    badge: str,
    badge_class: str,
    subtext: str,
) -> str:
    return (
        f'<div class="bento-kpi-card accent-{accent}">'
        f'<div class="kpi-top">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<span class="kpi-badge {badge_class}">{html.escape(badge)}</span>'
        f"</div>"
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-subtext">{html.escape(subtext)}</div>'
        f"</div>"
    )


def render_kpis(
    sales_df: pd.DataFrame,
    customers_df: pd.DataFrame,
    reviews_df: pd.DataFrame,
) -> None:
    render_section_header(
        "Executive Pulse",
        "Top-line performance for the active filter window.",
    )

    total_rev = float(_numeric(sales_df, "total_order_value").sum())

    if sales_df is not None and not sales_df.empty and "order_id" in sales_df.columns:
        total_orders = int(sales_df["order_id"].nunique())
    else:
        total_orders = 0

    if (
        customers_df is not None
        and not customers_df.empty
        and "customer_unique_id" in customers_df.columns
    ):
        total_customers = int(customers_df["customer_unique_id"].nunique())
    else:
        total_customers = 0

    avg_rating = _weighted_average_rating(reviews_df)
    reviewed_orders = int(_numeric(reviews_df, "average_score").shape[0])

    if sales_df is not None and not sales_df.empty:
        state_count = (
            int(sales_df["customer_state"].nunique())
            if "customer_state" in sales_df.columns
            else 0
        )
        city_count = (
            int(sales_df["customer_city"].nunique())
            if "customer_city" in sales_df.columns
            else 0
        )
    else:
        state_count = 0
        city_count = 0

    average_order_value = total_rev / total_orders if total_orders else 0.0

    if (
        customers_df is not None
        and not customers_df.empty
        and "lifetime_orders" in customers_df.columns
    ):
        lifetime_orders = pd.to_numeric(
            customers_df["lifetime_orders"], errors="coerce"
        )
        repeat_customers = int((lifetime_orders > 1).sum())
    else:
        repeat_customers = 0

    repeat_ratio = (
        repeat_customers / total_customers if total_customers > 0 else 0.0
    )
    top_state = _top_state(customers_df)
    rating_label = _rating_label(avg_rating)
    stars = _rating_stars(avg_rating)

    revenue_badge = (
        f"AOV ${average_order_value:,.2f}" if total_orders else "No orders"
    )
    revenue_badge_class = "positive" if total_orders else "neutral"
    orders_badge = f"{state_count} states" if state_count else "No regions"
    customers_badge = (
        f"{repeat_ratio:.0%} repeat" if total_customers else "No customers"
    )
    customers_badge_class = (
        "positive" if repeat_ratio >= 0.25 else "neutral"
    )
    rating_badge = f"{stars}"
    rating_badge_class = "stars"

    revenue_subtext = (
        f"{total_orders:,} orders in the active window"
        if total_orders
        else "No sales rows in the active window"
    )
    orders_subtext = (
        f"{state_count} states · {city_count} cities"
        if total_orders
        else "Fulfillment context unavailable"
    )
    customers_subtext = (
        f"{repeat_customers:,} repeat buyers · top market {top_state}"
        if top_state
        else f"{total_customers:,} unique buyers in view"
    )
    rating_subtext = (
        f"{rating_label} · {reviewed_orders:,} reviewed orders"
        if reviewed_orders
        else "No review scores in the active window"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            _bento_card(
                "emerald",
                "Total Revenue",
                f"${total_rev:,.2f}",
                revenue_badge,
                revenue_badge_class,
                revenue_subtext,
            ),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            _bento_card(
                "indigo",
                "Total Orders",
                f"{total_orders:,}",
                orders_badge,
                "accent" if state_count else "neutral",
                orders_subtext,
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            _bento_card(
                "cyan",
                "Unique Customers",
                f"{total_customers:,}",
                customers_badge,
                customers_badge_class,
                customers_subtext,
            ),
            unsafe_allow_html=True,
        )

    rating_value = (
        f'{avg_rating:.2f}<span class="kpi-denom"> / 5.00</span>'
        if reviewed_orders
        else "0.00"
    )
    with col4:
        st.markdown(
            _bento_card(
                "amber",
                "Customer Satisfaction",
                rating_value,
                rating_badge if reviewed_orders else "No reviews",
                rating_badge_class if reviewed_orders else "neutral",
                rating_subtext,
            ),
            unsafe_allow_html=True,
        )
