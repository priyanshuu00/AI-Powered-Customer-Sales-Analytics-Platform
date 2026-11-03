"""Sidebar filters, data-source badge, and live data controls."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.database import (
    get_data_source_status,
    get_source_class,
    get_source_label,
    reset_data_source,
    reset_to_baseline,
    simulate_new_orders,
)

FILTER_KEYS = ("date_range_filter", "state_filter")
DATE_FILTER_KEY = "date_range_filter"

_LAST_SIMULATION_KEY = "_last_simulation"
_SIMULATION_ERROR_KEY = "_simulation_error"
_BASELINE_RESET_KEY = "_baseline_reset"


def _render_status_badge() -> None:
    status = get_data_source_status()
    mode = status.get("mode", "unknown")

    css_class = get_source_class(mode)
    label = get_source_label(mode)

    st.sidebar.markdown(
        f'<div class="status-badge status-{css_class}">'
        f'<span class="dot"></span>{label}</div>',
        unsafe_allow_html=True,
    )

    message = status.get("message")
    if message:
        st.sidebar.caption(message)


def _reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def _render_live_controls() -> None:
    """Sidebar controls that mutate the active dataset in real time."""

    with st.sidebar.expander("⚡ Live Data Controls", expanded=False):
        st.caption(
            "Inject realistic transactions into the active engine, or restore "
            "the clean baseline dataset."
        )

        batch_size = st.slider(
            "New orders to simulate",
            min_value=25,
            max_value=500,
            value=50,
            step=25,
            key="simulate_batch_size",
            help="Orders are dated through 2026 and appended to every view.",
        )

        if st.button(
            "➕ Simulate New Orders",
            key="simulate_orders_button",
            width="stretch",
        ):
            try:
                stats = simulate_new_orders(int(batch_size))
            except Exception as exc:  # noqa: BLE001 - keep the sidebar usable
                st.session_state[_SIMULATION_ERROR_KEY] = (
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                st.session_state[_LAST_SIMULATION_KEY] = stats
                st.session_state.pop(_SIMULATION_ERROR_KEY, None)
                st.session_state[_BASELINE_RESET_KEY] = None
                st.session_state.pop(DATE_FILTER_KEY, None)
            st.rerun()

        if st.button(
            "🔄 Reset to Baseline Dataset",
            key="reset_baseline_button",
            width="stretch",
        ):
            reset_ok = reset_to_baseline()
            st.session_state[_LAST_SIMULATION_KEY] = None
            st.session_state.pop(_SIMULATION_ERROR_KEY, None)
            st.session_state[_BASELINE_RESET_KEY] = reset_ok
            _reset_filters()
            st.rerun()

        error = st.session_state.get(_SIMULATION_ERROR_KEY)
        if error:
            st.error(error)

        last = st.session_state.get(_LAST_SIMULATION_KEY)
        if isinstance(last, dict) and last.get("orders_added"):
            st.caption(
                f"Added {int(last['orders_added']):,} orders · "
                f"+${float(last.get('revenue_added', 0.0)):,.2f} revenue · "
                f"{int(last.get('customers_added', 0)):,} new customers · "
                f"{int(last.get('reviews_added', 0)):,} reviews"
            )

        if st.session_state.get(_BASELINE_RESET_KEY):
            st.caption("Baseline dataset restored.")


def render_sidebar(df_sales_summary: pd.DataFrame) -> dict:
    st.sidebar.header("Global Filters")
    _render_status_badge()
    _render_live_controls()

    if st.sidebar.button("Reset Filters", key="reset_filters_button"):
        _reset_filters()
        st.rerun()

    if st.sidebar.button("Retry live connection", key="retry_live_button"):
        reset_data_source()
        st.rerun()

    filters: dict = {}

    if df_sales_summary is None or df_sales_summary.empty:
        st.sidebar.caption("No sales rows available for filtering.")
        return filters

    if "order_purchase_timestamp" in df_sales_summary.columns:
        timestamps = pd.to_datetime(
            df_sales_summary["order_purchase_timestamp"], errors="coerce"
        ).dropna()
        if not timestamps.empty:
            min_date = timestamps.min().date()
            max_date = timestamps.max().date()
            date_range = st.sidebar.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=DATE_FILTER_KEY,
            )
            if hasattr(date_range, "__len__") and len(date_range) == 2:
                filters["date_range"] = date_range

    if "customer_state" in df_sales_summary.columns:
        states = sorted(df_sales_summary["customer_state"].dropna().unique())
        filters["state"] = st.sidebar.multiselect(
            "State Filter",
            options=states,
            key="state_filter",
        )

    return filters
