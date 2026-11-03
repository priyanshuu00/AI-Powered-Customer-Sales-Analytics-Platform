"""Reusable dataframe filters for the dashboard."""

from typing import Iterable, Optional

import pandas as pd

# First column found on a frame is treated as its date axis.
DATE_COLUMNS = (
    "order_purchase_timestamp",
    "review_creation_date",
    "purchase_date",
    "sale_month",
)


def apply_date_filter(df: pd.DataFrame, date_range: Optional[Iterable]) -> pd.DataFrame:
    """Filter a date-aware frame by an inclusive ``(start, end)`` range.

    Frames without a recognised date column, empty frames, and incomplete
    ranges are returned unchanged.
    """

    if df is None or df.empty or date_range is None:
        return df

    try:
        values = list(date_range)
    except TypeError:
        return df

    if len(values) != 2 or values[0] is None or values[1] is None:
        return df

    column = next((name for name in DATE_COLUMNS if name in df.columns), None)
    if column is None:
        return df

    try:
        dates = pd.to_datetime(df[column], errors="coerce")
        start = pd.to_datetime(values[0])
        end = pd.to_datetime(values[1])
    except (TypeError, ValueError):
        return df

    if dates.isna().all():
        return df

    mask = (
        dates.notna()
        & (dates.dt.normalize() >= start.normalize())
        & (dates.dt.normalize() <= end.normalize())
    )
    return df.loc[mask].copy()


def apply_global_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply state, city, category, and payment-type filters when present."""

    filtered_df = df.copy()

    if filters.get("state") and "customer_state" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["customer_state"].isin(filters["state"])
        ]

    if filters.get("city") and "customer_city" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["customer_city"].isin(filters["city"])]

    if filters.get("category") and "category_name" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["category_name"].isin(filters["category"])]

    if filters.get("payment_type") and "payment_type" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["payment_type"].isin(filters["payment_type"])
        ]

    return filtered_df
