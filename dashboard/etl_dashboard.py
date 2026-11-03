"""Data Studio & ETL tab.

Exposes the storage architecture, an interactive dataset inspector, and a
one-click synthetic-data seeder that runs the real ``etl`` package inside a
visual progress container. It works with MySQL online or offline: when the
dashboard is in demo mode the load stage is skipped instead of failing.
"""

from __future__ import annotations

import html
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from dashboard.database import (
    apply_custom_views_from_frame,
    clear_custom_views,
    get_custom_views,
    get_data_source_status,
    get_source_class,
    get_source_label,
    has_custom_views,
    reset_data_source,
)
from dashboard.theme import render_section_header
from etl.config import FILE_PATHS, RAW_DATA_DIR
from etl.pipeline import run_pipeline
from etl.sample_data import seed_sample_raw_csvs

_LAST_RUN_KEY = "etl_last_run"
_LAST_APPLY_KEY = "etl_last_apply"

_APPLY_VIEW_OPTIONS: Dict[str, Optional[str]] = {
    "Auto-detect (unified orders CSV or one dashboard view)": None,
    "sales_summary": "sales_summary",
    "customer_segments": "customer_segments",
    "product_performance": "product_performance",
    "payment_analysis": "payment_analysis",
    "review_summary": "review_summary",
}

_FILTER_STATE_KEYS = ("date_range_filter", "state_filter")

DATASETS: Dict[str, str] = {
    "sales_summary": "📈 Sales Summary",
    "customer_segments": "👥 Customer Segments",
    "product_performance": "📦 Product Performance",
    "payment_analysis": "💳 Payment Analysis",
    "review_summary": "⭐ Review Summary",
}

_UPLOAD_LABEL = "⬆ Custom CSV upload"

_STAGE_ICONS = {
    "success": "✓",
    "error": "✕",
    "skipped": "–",
    "running": "•",
}


def _frame_map(
    sales_df: Optional[pd.DataFrame],
    customer_df: Optional[pd.DataFrame],
    product_df: Optional[pd.DataFrame],
    payment_df: Optional[pd.DataFrame],
    review_df: Optional[pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    candidates = {
        "sales_summary": sales_df,
        "customer_segments": customer_df,
        "product_performance": product_df,
        "payment_analysis": payment_df,
        "review_summary": review_df,
    }
    return {
        key: value if isinstance(value, pd.DataFrame) else pd.DataFrame()
        for key, value in candidates.items()
    }


# --------------------------------------------------------------------------- #
# Architecture cards
# --------------------------------------------------------------------------- #


def _render_architecture(frames: Dict[str, pd.DataFrame]) -> None:
    status = get_data_source_status()
    mode = status.get("mode", "unknown")
    mode_class = get_source_class(mode)
    mode_label = get_source_label(mode)

    total_rows = int(sum(len(frame) for frame in frames.values()))
    present = sum(1 for path in FILE_PATHS.values() if Path(path).exists())
    expected = len(FILE_PATHS)

    st.markdown(
        f'<div class="studio-grid">'
        f'<div class="studio-card">'
        f'<div class="studio-label">Data Source</div>'
        f'<div class="studio-value"><span class="status-pill {mode_class}">'
        f'<span class="dot"></span>{html.escape(mode_label)}</span></div>'
        f'<div class="studio-sub">{html.escape(str(status.get("message", "")))}</div>'
        f"</div>"
        f'<div class="studio-card">'
        f'<div class="studio-label">Active Dataset Rows</div>'
        f'<div class="studio-value mono">{total_rows:,}</div>'
        f'<div class="studio-sub">across {len(frames)} dashboard views</div>'
        f"</div>"
        f'<div class="studio-card">'
        f'<div class="studio-label">Raw CSV Vault</div>'
        f'<div class="studio-value mono">{present}/{expected}</div>'
        f'<div class="studio-sub">{html.escape(str(RAW_DATA_DIR))}</div>'
        f"</div>"
        f'<div class="studio-card">'
        f'<div class="studio-label">Pipeline Contract</div>'
        f'<div class="studio-value">Extract → Validate → Transform → Load</div>'
        f'<div class="studio-sub">structured result dict · UTF-8 ETL report</div>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    tiles = "".join(
        f'<div class="studio-dataset-tile">'
        f'<div class="studio-dataset-name">{html.escape(DATASETS[key])}</div>'
        f'<div class="studio-dataset-rows mono">{len(frames[key]):,}</div>'
        f"</div>"
        for key in DATASETS
    )
    st.markdown(f'<div class="studio-dataset-grid">{tiles}</div>', unsafe_allow_html=True)

    with st.expander("Raw CSV vault status", expanded=False):
        rows = []
        for name, path in FILE_PATHS.items():
            resolved = Path(path)
            rows.append(
                {
                    "Dataset": name,
                    "File": resolved.name,
                    "Folder": "data/raw" if resolved.parent == Path(RAW_DATA_DIR) else "data",
                    "Status": "Present" if resolved.exists() else "Missing",
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# Dataset inspector
# --------------------------------------------------------------------------- #


def _profile_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Column": df.columns,
            "Type": [str(dtype) for dtype in df.dtypes],
            "Non-null": df.notna().sum().to_numpy(),
            "Missing": df.isna().sum().to_numpy(),
            "Missing %": (df.isna().mean() * 100).round(1).to_numpy(),
            "Unique": [int(df[column].nunique(dropna=True)) for column in df.columns],
        }
    )


def _render_inspector(frames: Dict[str, pd.DataFrame]) -> None:
    options = list(DATASETS) + [_UPLOAD_LABEL]
    choice = st.selectbox(
        "Select a dataset to inspect",
        options=options,
        format_func=lambda key: DATASETS.get(key, key),
        key="etl_dataset_choice",
    )

    if choice == _UPLOAD_LABEL:
        uploaded = st.file_uploader(
            "Upload a CSV to inspect",
            type=["csv"],
            key="etl_upload",
        )
        if uploaded is None:
            st.caption(
                "Upload a CSV, or pick one of the five active dashboard datasets."
            )
            return
        try:
            df = pd.read_csv(uploaded)
            name = Path(uploaded.name).stem or "uploaded_dataset"
        except Exception as exc:  # noqa: BLE001 - user-provided file
            st.caption(f"Could not parse the uploaded CSV: {type(exc).__name__}: {exc}")
            return
    else:
        df = frames.get(choice, pd.DataFrame())
        name = choice

    if df is None or df.empty:
        st.caption(f"{DATASETS.get(choice, choice)} has no rows in the active filter.")
        return

    row_columns = st.columns(4)
    with row_columns[0]:
        st.metric("Rows", f"{len(df):,}")
    with row_columns[1]:
        st.metric("Columns", f"{df.shape[1]:,}")
    with row_columns[2]:
        st.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")
    with row_columns[3]:
        numeric_cols = df.select_dtypes(include="number").shape[1]
        st.metric("Numeric Columns", f"{numeric_cols:,}")

    render_section_header(
        "Schema & Completeness",
        "Column types, null coverage, and cardinality for the selected dataset.",
    )
    st.dataframe(_profile_frame(df), hide_index=True, width="stretch")

    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        with st.expander("Summary statistics (numeric columns)", expanded=False):
            st.dataframe(numeric.describe().T, width="stretch")

    categorical = df.select_dtypes(exclude="number")
    if not categorical.empty:
        with st.expander("Top categorical values", expanded=False):
            for column in list(categorical.columns)[:4]:
                counts = df[column].astype(str).value_counts().head(5)
                if counts.empty:
                    continue
                st.markdown(f"**{column}**")
                st.dataframe(
                    counts.rename_axis("Value").reset_index(name="Rows"),
                    hide_index=True,
                    width="stretch",
                )

    render_section_header(
        "Preview",
        "First 50 rows of the selected dataset.",
    )
    st.dataframe(df.head(50), hide_index=True, width="stretch")

    st.download_button(
        "⬇ Export dataset CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{name}.csv",
        mime="text/csv",
        key="etl_export_button",
    )


# --------------------------------------------------------------------------- #
# Seeder + pipeline runner
# --------------------------------------------------------------------------- #


def _stage_rows(stages) -> str:
    blocks = []
    for entry in stages:
        status = str(entry.get("status", "running"))
        icon = _STAGE_ICONS.get(status, "•")
        blocks.append(
            f'<div class="etl-stage {html.escape(status)}">'
            f'<span class="etl-stage-icon">{icon}</span>'
            f'<span class="etl-stage-name">{html.escape(str(entry.get("name", "")))}</span>'
            f'<span class="etl-stage-detail">{html.escape(str(entry.get("detail", "")))}</span>'
            f"</div>"
        )
    return "".join(blocks)


def _render_last_run() -> None:
    payload = st.session_state.get(_LAST_RUN_KEY)
    if not isinstance(payload, dict):
        return

    result = payload.get("result") or {}
    seed = payload.get("seed") or {}
    status = str(result.get("status", "unknown"))

    render_section_header(
        "Last Pipeline Run",
        f"Completed at {payload.get('at', '—')} · status: {status}.",
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Rows Extracted", f"{int(result.get('rows_extracted', 0)):,}")
    with metric_columns[1]:
        st.metric("Rows Cleaned", f"{int(result.get('rows_transformed', 0)):,}")
    with metric_columns[2]:
        st.metric("Rows Removed", f"{int(result.get('rows_removed', 0)):,}")
    with metric_columns[3]:
        st.metric("Rows Loaded", f"{int(result.get('rows_loaded', 0)):,}")

    created = seed.get("created") or []
    skipped = seed.get("skipped") or []
    if created or skipped:
        st.caption(
            f"Sample CSVs · {len(created)} created · {len(skipped)} already present "
            f"in {seed.get('raw_dir', RAW_DATA_DIR)} · "
            f"seed {seed.get('seed', '—')} · "
            f"{seed.get('total_orders', 0)} orders"
        )

    load_target = result.get("load_target")
    if load_target:
        target_copy = (
            f"MySQL warehouse"
            if load_target == "mysql"
            else f"embedded SQLite · {result.get('sqlite_path') or ''}"
        )
        st.caption(f"Load target · {target_copy}")

    views_written = result.get("views_written") or {}
    if views_written:
        st.caption(
            "Analytical views · "
            + " · ".join(
                f"{name} ({rows:,})" for name, rows in views_written.items()
            )
        )

    st.markdown(
        f'<div class="etl-stage-list">{_stage_rows(result.get("stages", []))}</div>',
        unsafe_allow_html=True,
    )

    validation = result.get("validation_stats") or {}
    if validation:
        with st.expander("Per-table validation detail", expanded=False):
            rows = []
            for table, stats in validation.items():
                rows.append(
                    {
                        "Table": table,
                        "Rows": stats.get("total_rows", 0),
                        "Duplicates": stats.get("duplicate_rows", 0),
                        "Missing cells": sum(
                            (stats.get("missing_values") or {}).values()
                        ),
                        "Null PKs": stats.get("null_pks", 0),
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    if result.get("report_path"):
        st.caption(f"ETL summary report · {result['report_path']}")

    if result.get("error"):
        st.caption(f"Pipeline note · {result['error']}")


def _run_seed_and_pipeline(
    overwrite: bool = False,
    seed: int = 7,
    order_multiplier: float = 1.0,
    regenerate: bool = False,
) -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if regenerate:
        seed = random.randint(1, 9_999_999)
        order_multiplier = round(random.uniform(0.7, 2.6), 2)

    seed_info: Dict[str, Any] = {
        "created": [],
        "skipped": [],
        "rows": {},
        "raw_dir": str(RAW_DATA_DIR),
        "seed": seed,
        "order_multiplier": order_multiplier,
        "total_orders": 0,
    }
    result: Dict[str, Any] = {"status": "error", "stages": [], "error": None}

    with st.status("Preparing sample data and running ETL...", expanded=True) as status_box:
        try:
            seed_info = seed_sample_raw_csvs(
                overwrite=overwrite,
                seed=seed,
                order_multiplier=order_multiplier,
            )
            st.write(
                f"Raw CSV vault · {len(seed_info['created'])} created · "
                f"{len(seed_info['skipped'])} skipped · "
                f"seed {seed_info.get('seed')} · "
                f"{seed_info.get('total_orders', 0)} orders · "
                f"{seed_info['raw_dir']}"
            )

            def progress(entry: Dict[str, Any]) -> None:
                icon = _STAGE_ICONS.get(str(entry.get("status")), "•")
                st.write(f"{icon} **{entry.get('name')}** — {entry.get('detail')}")

            result = run_pipeline(
                raise_on_error=False,
                load=True,
                progress_callback=progress,
            )

            label = (
                "ETL pipeline complete"
                if result.get("status") == "success"
                else "ETL pipeline finished with notes"
            )
            status_box.update(label=label, state="complete", expanded=False)
        except Exception as exc:  # noqa: BLE001 - keep the tab interactive
            result["error"] = f"{type(exc).__name__}: {exc}"
            st.caption(f"ETL run aborted · {result['error']}")
            status_box.update(
                label="ETL run aborted", state="complete", expanded=False
            )

    st.session_state[_LAST_RUN_KEY] = {
        "seed": seed_info,
        "result": result,
        "at": started_at,
    }

    # Force the dashboard to re-probe the active engine and drop cached queries.
    reset_data_source()
    for key in _FILTER_STATE_KEYS:
        st.session_state.pop(key, None)


def _render_runner() -> None:
    render_section_header(
        "Synthetic Data Seeder & ETL Runner",
        "Generates schema-valid Olist CSVs in data/raw, then runs "
        "Extract → Validate → Transform → Load into MySQL or the embedded "
        "SQLite engine, with live stage telemetry.",
    )

    missing = [Path(path).name for path in FILE_PATHS.values() if not Path(path).exists()]
    if missing:
        st.caption(
            f"{len(missing)} of {len(FILE_PATHS)} expected raw files are missing. "
            "Seeding will create only the absent files, so real Olist data is "
            "never overwritten."
        )
    else:
        st.caption(
            "All expected raw files are present. Existing CSVs are reused rather "
            "than overwritten."
        )

    if st.button(
        "Seed Sample Raw CSVs & Run ETL Pipeline",
        key="etl_seed_run_button",
        type="primary",
        width="stretch",
    ):
        _run_seed_and_pipeline()
        st.rerun()

    if st.button(
        "🎲 Regenerate Raw Dataset (New Random Seed) & Run ETL",
        key="etl_regenerate_button",
        width="stretch",
        help=(
            "Overwrites the raw CSVs with a freshly randomised dataset size "
            "and distribution, then reloads the active database."
        ),
    ):
        _run_seed_and_pipeline(overwrite=True, regenerate=True)
        st.rerun()

    _render_last_run()


# --------------------------------------------------------------------------- #
# Uploaded CSV -> live dashboard
# --------------------------------------------------------------------------- #


def _render_csv_apply() -> None:
    render_section_header(
        "Apply Uploaded CSV to Live Dashboard",
        "Upload a unified e-commerce orders CSV (auto-derives all five views) "
        "or a single view CSV such as sales_summary. The upload immediately "
        "drives KPIs, charts, and the AI Copilot.",
    )

    uploaded = st.file_uploader(
        "CSV to apply to the dashboard",
        type=["csv"],
        key="etl_apply_upload",
        help=(
            "Unified orders CSV: order_id, date, value, plus optional customer, "
            "category, payment, and review columns."
        ),
    )

    mapping_label = st.selectbox(
        "CSV type",
        options=list(_APPLY_VIEW_OPTIONS),
        key="etl_apply_view",
        help="Choose Auto-detect unless you are uploading a single dashboard view.",
    )

    if st.button(
        "Apply Uploaded CSV to Live Dashboard",
        key="etl_apply_csv_button",
        type="primary",
        width="stretch",
    ):
        if uploaded is None:
            st.warning("Choose a CSV file first.")
        else:
            try:
                frame = pd.read_csv(uploaded)
                summary = apply_custom_views_from_frame(
                    frame,
                    view_key=_APPLY_VIEW_OPTIONS[mapping_label],
                    source_name=uploaded.name,
                )
            except Exception as exc:  # noqa: BLE001 - user-provided file
                st.error(
                    f"Could not apply {uploaded.name}: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                st.session_state[_LAST_APPLY_KEY] = {
                    **summary,
                    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "file": uploaded.name,
                }
                for key in _FILTER_STATE_KEYS:
                    st.session_state.pop(key, None)
                st.rerun()

    if has_custom_views():
        if st.button(
            "Clear Custom Data & Return to Live Engine",
            key="etl_clear_custom_button",
            width="stretch",
        ):
            clear_custom_views()
            st.session_state[_LAST_APPLY_KEY] = None
            reset_data_source()
            for key in _FILTER_STATE_KEYS:
                st.session_state.pop(key, None)
            st.rerun()

    summary = st.session_state.get(_LAST_APPLY_KEY)
    if not isinstance(summary, dict):
        return

    st.caption(
        f"Applied {summary.get('source', 'CSV')} at {summary.get('at', '—')} · "
        f"{summary.get('total_rows', 0):,} rows · "
        f"views: {', '.join(summary.get('views', []))}"
    )

    columns = st.columns(4)
    rows = summary.get("rows") or {}
    with columns[0]:
        st.metric("Uploaded Rows", f"{int(summary.get('total_rows', 0)):,}")
    with columns[1]:
        st.metric("Derived Views", f"{len(summary.get('views', [])):,}")
    with columns[2]:
        st.metric(
            "Sales Rows",
            f"{int(rows.get('sales_summary', 0)):,}",
        )
    with columns[3]:
        st.metric(
            "Review Rows",
            f"{int(rows.get('review_summary', 0)):,}",
        )

    for note in summary.get("notes", []):
        st.caption(f"• {note}")

    applied_views = get_custom_views()
    preview_keys = [
        key for key in summary.get("views", []) if key in applied_views
    ]
    if preview_keys:
        with st.expander("Preview applied views", expanded=False):
            for key in preview_keys:
                st.markdown(f"**{DATASETS.get(key, key)}**")
                st.dataframe(
                    applied_views[key].head(10),
                    hide_index=True,
                    width="stretch",
                )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def render_etl_dashboard(
    sales_df: Optional[pd.DataFrame],
    customer_df: Optional[pd.DataFrame],
    product_df: Optional[pd.DataFrame],
    payment_df: Optional[pd.DataFrame],
    review_df: Optional[pd.DataFrame],
) -> None:
    frames = _frame_map(sales_df, customer_df, product_df, payment_df, review_df)

    render_section_header(
        "Data Studio & ETL",
        "Storage topology, dataset profiling, and a one-click pipeline runner.",
    )

    _render_architecture(frames)

    render_section_header(
        "Interactive Dataset Inspector",
        "Inspect schema, missing values, statistics, and preview rows.",
    )
    _render_inspector(frames)

    _render_csv_apply()

    _render_runner()
