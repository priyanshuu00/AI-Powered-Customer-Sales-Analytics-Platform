"""Embedded SQLite analytics store for cloud deployments.

This module is the persistence core behind the dashboard's Tier-2
``live_sqlite`` data source. It has no Streamlit dependency, so the ETL
pipeline, tests, and the CLI can use it directly.

Responsibilities
----------------
* Resolve and cache the SQLite engine at ``data/processed/analytics_live.db``.
* Derive the five analytical dashboard views from the transformed Olist
  tables (the same views MySQL exposes through ``vw_*``).
* Write raw tables + analytical tables + real SQL views on first run, so the
  dashboard can query ``SELECT * FROM vw_sales_summary`` exactly as it does
  against MySQL.
* Simulate new orders and apply uploaded CSVs without any external database.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "processed" / "analytics_live.db"

# Logical view name -> SQL view that the dashboard queries.
VIEW_SQL_NAMES: Dict[str, str] = {
    "sales_summary": "vw_sales_summary",
    "customer_segments": "vw_customer_summary",
    "product_performance": "vw_category_performance",
    "payment_analysis": "vw_payment_summary",
    "review_summary": "vw_review_summary",
}

VIEW_QUERIES: Dict[str, str] = {
    key: f"SELECT * FROM {sql_name};" for key, sql_name in VIEW_SQL_NAMES.items()
}

VIEW_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "sales_summary": (
        "order_id",
        "order_status",
        "order_purchase_timestamp",
        "customer_state",
        "customer_city",
        "total_order_value",
    ),
    "customer_segments": (
        "customer_unique_id",
        "customer_city",
        "customer_state",
        "lifetime_orders",
        "lifetime_spent",
    ),
    "product_performance": (
        "category_name",
        "total_units_sold",
        "total_category_revenue",
        "sale_month",
    ),
    "payment_analysis": (
        "payment_type",
        "transaction_count",
        "total_volume",
        "average_transaction_value",
        "sale_month",
    ),
    "review_summary": (
        "order_id",
        "average_score",
        "review_count",
        "review_creation_date",
    ),
}

VIEW_KEYS: Tuple[str, ...] = tuple(VIEW_COLUMNS)

RAW_TABLE_NAMES: Tuple[str, ...] = (
    "geolocation",
    "customers",
    "sellers",
    "products",
    "category_translation",
    "orders",
    "order_items",
    "payments",
    "reviews",
)

_ENGINES: Dict[str, Engine] = {}


# --------------------------------------------------------------------------- #
# Engine / path helpers
# --------------------------------------------------------------------------- #


def get_sqlite_path(path: Optional[Path | str] = None) -> Path:
    """Resolve the active SQLite file, honouring ``ANALYTICS_SQLITE_PATH``."""

    if path is not None:
        return Path(path)

    override = (os.getenv("ANALYTICS_SQLITE_PATH") or "").strip()
    return Path(override).expanduser() if override else DEFAULT_SQLITE_PATH


def get_sqlite_engine(path: Optional[Path | str] = None) -> Engine:
    """Return a cached SQLAlchemy engine for the embedded store."""

    resolved = get_sqlite_path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    key = str(resolved)

    engine = _ENGINES.get(key)
    if engine is None:
        engine = create_engine(
            f"sqlite:///{resolved.as_posix()}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        _ENGINES[key] = engine
    return engine


def dispose_sqlite_engines(path: Optional[Path | str] = None) -> None:
    """Dispose one or all cached SQLite engines (needed before file deletes)."""

    if path is not None:
        key = str(get_sqlite_path(path).resolve())
        engine = _ENGINES.pop(key, None)
        if engine is not None:
            engine.dispose()
        return

    for engine in list(_ENGINES.values()):
        try:
            engine.dispose()
        except Exception:  # pragma: no cover - defensive
            pass
    _ENGINES.clear()


# --------------------------------------------------------------------------- #
# Frame helpers
# --------------------------------------------------------------------------- #


def _empty_frame(columns: Sequence[str]) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series(dtype="object") for column in columns})


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _text_column(frame: pd.DataFrame, column: str, fallback: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(fallback, index=frame.index, dtype="object")
    return frame[column].fillna(fallback).astype(str)


def _month_series(values: pd.Series) -> pd.Series:
    """Normalise a timestamp/mixed series to ``YYYY-MM`` strings."""

    text_values = values.astype(str).str.strip()
    parsed = pd.to_datetime(values, errors="coerce")
    months = parsed.dt.strftime("%Y-%m")
    fallback = text_values.str.slice(0, 7)
    fallback = fallback.where(fallback.str.match(r"^\d{4}-\d{2}$"))
    return months.fillna(fallback)


# --------------------------------------------------------------------------- #
# Analytical view derivation
# --------------------------------------------------------------------------- #


def _build_sales(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = frames.get("orders", pd.DataFrame())
    if orders.empty or "order_id" not in orders.columns:
        return _empty_frame(VIEW_COLUMNS["sales_summary"])

    sales = orders.copy()
    customers = frames.get("customers", pd.DataFrame())
    if (
        not customers.empty
        and "customer_id" in customers.columns
        and "customer_id" in sales.columns
    ):
        customer_columns = [
            column
            for column in ("customer_id", "customer_state", "customer_city")
            if column in customers.columns
        ]
        sales = sales.merge(
            customers[customer_columns].drop_duplicates("customer_id"),
            on="customer_id",
            how="left",
        )

    items = frames.get("order_items", pd.DataFrame())
    if not items.empty and "order_id" in items.columns:
        line = items.copy()
        line["_line_value"] = (
            _numeric(line, "price").fillna(0)
            + _numeric(line, "freight_value").fillna(0)
        )
        totals = (
            line.groupby("order_id", as_index=False)["_line_value"]
            .sum()
            .rename(columns={"_line_value": "_items_value"})
        )
        sales = sales.merge(totals, on="order_id", how="left")
    else:
        sales["_items_value"] = np.nan

    payments = frames.get("payments", pd.DataFrame())
    if (
        not payments.empty
        and "order_id" in payments.columns
        and "payment_value" in payments.columns
    ):
        paid = (
            payments.assign(_paid=_numeric(payments, "payment_value").fillna(0))
            .groupby("order_id", as_index=False)["_paid"]
            .sum()
            .rename(columns={"_paid": "_payment_value"})
        )
        sales = sales.merge(paid, on="order_id", how="left")
    else:
        sales["_payment_value"] = np.nan

    sales["total_order_value"] = (
        _numeric(sales, "_items_value")
        .fillna(_numeric(sales, "_payment_value"))
        .fillna(0.0)
        .round(2)
    )

    if "order_purchase_timestamp" in sales.columns:
        sales["order_purchase_timestamp"] = pd.to_datetime(
            sales["order_purchase_timestamp"], errors="coerce"
        )
    else:
        sales["order_purchase_timestamp"] = pd.NaT

    sales["order_status"] = _text_column(sales, "order_status", "delivered")
    sales["customer_state"] = _text_column(sales, "customer_state", "unknown")
    sales["customer_city"] = _text_column(sales, "customer_city", "unknown")

    result = sales.loc[:, list(VIEW_COLUMNS["sales_summary"])].copy()
    return result.sort_values("order_purchase_timestamp", ignore_index=True)


def _build_customers(
    frames: Dict[str, pd.DataFrame], sales: pd.DataFrame
) -> pd.DataFrame:
    if sales.empty or "order_id" not in sales.columns:
        return _empty_frame(VIEW_COLUMNS["customer_segments"])

    customers = frames.get("customers", pd.DataFrame())
    if (
        not customers.empty
        and "customer_id" in customers.columns
        and "customer_id" in sales.columns
    ):
        key_column = (
            "customer_unique_id"
            if "customer_unique_id" in customers.columns
            else "customer_id"
        )
        mapping = customers[
            ["customer_id", key_column]
        ].drop_duplicates("customer_id")
        merged = sales.merge(mapping, on="customer_id", how="left")
        keys = merged[key_column].fillna(merged["order_id"])
        work = pd.DataFrame(
            {
                "_customer_key": keys,
                "customer_city": merged["customer_city"],
                "customer_state": merged["customer_state"],
                "order_id": merged["order_id"],
                "total_order_value": merged["total_order_value"],
            }
        )
    else:
        work = pd.DataFrame(
            {
                "_customer_key": sales["order_id"],
                "customer_city": sales["customer_city"],
                "customer_state": sales["customer_state"],
                "order_id": sales["order_id"],
                "total_order_value": sales["total_order_value"],
            }
        )

    grouped = (
        work.groupby("_customer_key", as_index=False)
        .agg(
            customer_city=("customer_city", "first"),
            customer_state=("customer_state", "first"),
            lifetime_orders=("order_id", "nunique"),
            lifetime_spent=("total_order_value", "sum"),
        )
        .rename(columns={"_customer_key": "customer_unique_id"})
    )
    grouped["lifetime_spent"] = grouped["lifetime_spent"].round(2)
    return grouped.sort_values("lifetime_spent", ascending=False, ignore_index=True)


def _build_products(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    items = frames.get("order_items", pd.DataFrame())
    if items.empty or "product_id" not in items.columns:
        return _empty_frame(VIEW_COLUMNS["product_performance"])

    work = items.copy()
    products = frames.get("products", pd.DataFrame())
    if not products.empty and "product_id" in products.columns:
        catalogue = products.copy()
        translation = frames.get("category_translation", pd.DataFrame())
        if (
            not translation.empty
            and "product_category_name" in catalogue.columns
            and "product_category_name" in translation.columns
        ):
            catalogue = catalogue.merge(
                translation, on="product_category_name", how="left"
            )

        if "product_category_name_english" in catalogue.columns:
            catalogue["category_name"] = catalogue[
                "product_category_name_english"
            ].fillna(
                catalogue.get(
                    "product_category_name", pd.Series("unknown", index=catalogue.index)
                )
            )
        elif "product_category_name" in catalogue.columns:
            catalogue["category_name"] = catalogue["product_category_name"]
        else:
            catalogue["category_name"] = "unknown"

        work = work.merge(
            catalogue[["product_id", "category_name"]],
            on="product_id",
            how="left",
        )
    else:
        work["category_name"] = "unknown"

    orders = frames.get("orders", pd.DataFrame())
    if (
        not orders.empty
        and "order_id" in orders.columns
        and "order_purchase_timestamp" in orders.columns
    ):
        work = work.merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        work["sale_month"] = _month_series(work["order_purchase_timestamp"])
    else:
        work["sale_month"] = pd.Timestamp.now().strftime("%Y-%m")

    work["sale_month"] = work["sale_month"].fillna(
        pd.Timestamp.now().strftime("%Y-%m")
    )
    work["category_name"] = _text_column(work, "category_name", "unknown")
    work["_units"] = (
        _numeric(work, "quantity").fillna(1)
        if "quantity" in work.columns
        else 1.0
    )
    work["_line_value"] = (
        _numeric(work, "price").fillna(0)
        + _numeric(work, "freight_value").fillna(0)
    )

    grouped = (
        work.groupby(["category_name", "sale_month"], as_index=False)
        .agg(
            total_units_sold=("_units", "sum"),
            total_category_revenue=("_line_value", "sum"),
        )
        .rename(columns={})
    )
    grouped["total_units_sold"] = grouped["total_units_sold"].round(0).astype(int)
    grouped["total_category_revenue"] = grouped["total_category_revenue"].round(2)
    return grouped


def _build_payments(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    payments = frames.get("payments", pd.DataFrame())
    if payments.empty or "order_id" not in payments.columns:
        return _empty_frame(VIEW_COLUMNS["payment_analysis"])

    work = payments.copy()
    orders = frames.get("orders", pd.DataFrame())
    if (
        not orders.empty
        and "order_id" in orders.columns
        and "order_purchase_timestamp" in orders.columns
    ):
        work = work.merge(
            orders[["order_id", "order_purchase_timestamp"]],
            on="order_id",
            how="left",
        )
        work["sale_month"] = _month_series(work["order_purchase_timestamp"])
    else:
        work["sale_month"] = pd.Timestamp.now().strftime("%Y-%m")

    work["sale_month"] = work["sale_month"].fillna(
        pd.Timestamp.now().strftime("%Y-%m")
    )
    work["payment_type"] = _text_column(work, "payment_type", "not_defined")
    work["_payment_value"] = _numeric(work, "payment_value").fillna(0)

    grouped = (
        work.groupby(["payment_type", "sale_month"], as_index=False)
        .agg(
            transaction_count=("_payment_value", "size"),
            total_volume=("_payment_value", "sum"),
        )
    )
    grouped["transaction_count"] = grouped["transaction_count"].astype(int)
    grouped["total_volume"] = grouped["total_volume"].round(2)
    grouped["average_transaction_value"] = (
        grouped["total_volume"]
        / grouped["transaction_count"].replace(0, np.nan)
    ).fillna(0.0).round(2)
    return grouped.loc[:, list(VIEW_COLUMNS["payment_analysis"])]


def _build_reviews(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    reviews = frames.get("reviews", pd.DataFrame())
    if reviews.empty or "order_id" not in reviews.columns:
        return _empty_frame(VIEW_COLUMNS["review_summary"])

    work = reviews.copy()
    work["_score"] = _numeric(work, "review_score")
    work = work.dropna(subset=["_score"])

    if "review_creation_date" in work.columns:
        work["_review_date"] = pd.to_datetime(
            work["review_creation_date"], errors="coerce"
        )
    else:
        work["_review_date"] = pd.NaT

    grouped = (
        work.groupby("order_id", as_index=False)
        .agg(
            average_score=("_score", "mean"),
            review_count=("_score", "size"),
            review_creation_date=("_review_date", "min"),
        )
    )
    grouped["average_score"] = grouped["average_score"].round(2)
    grouped["review_count"] = grouped["review_count"].astype(int)
    return grouped.loc[:, list(VIEW_COLUMNS["review_summary"])]


def derive_views(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Derive the five dashboard views from transformed Olist tables."""

    frames = {
        name: (frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame())
        for name, frame in (dfs or {}).items()
    }

    views: Dict[str, pd.DataFrame] = {
        key: _empty_frame(columns) for key, columns in VIEW_COLUMNS.items()
    }

    builders = (
        ("sales_summary", lambda: _build_sales(frames)),
        (
            "customer_segments",
            lambda: _build_customers(frames, views["sales_summary"]),
        ),
        ("product_performance", lambda: _build_products(frames)),
        ("payment_analysis", lambda: _build_payments(frames)),
        ("review_summary", lambda: _build_reviews(frames)),
    )

    for key, builder in builders:
        try:
            views[key] = builder()
        except Exception as exc:  # pragma: no cover - defensive per-view guard
            logger.warning("Could not derive view %s: %s", key, exc)
            views[key] = _empty_frame(VIEW_COLUMNS[key])

    return views


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def _create_sql_views(connection) -> None:
    for key in VIEW_KEYS:
        sql_name = VIEW_SQL_NAMES[key]
        connection.exec_driver_sql(f'DROP VIEW IF EXISTS "{sql_name}"')
        connection.exec_driver_sql(
            f'CREATE VIEW "{sql_name}" AS SELECT * FROM "{key}"'
        )


def write_views(
    views: Dict[str, pd.DataFrame],
    raw_frames: Optional[Dict[str, pd.DataFrame]] = None,
    path: Optional[Path | str] = None,
) -> Dict[str, int]:
    """Persist analytical views (and optionally raw tables) into SQLite."""

    engine = get_sqlite_engine(path)
    written: Dict[str, int] = {}

    with engine.begin() as connection:
        if raw_frames:
            for name, frame in raw_frames.items():
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    frame.to_sql(
                        name,
                        connection,
                        if_exists="replace",
                        index=False,
                        chunksize=5000,
                    )

        for key in VIEW_KEYS:
            frame = views.get(key)
            if not isinstance(frame, pd.DataFrame):
                frame = _empty_frame(VIEW_COLUMNS[key])
            frame.to_sql(
                key,
                connection,
                if_exists="replace",
                index=False,
                chunksize=5000,
            )
            written[key] = int(len(frame))

        _create_sql_views(connection)

    return written


def read_sqlite_views(path: Optional[Path | str] = None) -> Dict[str, pd.DataFrame]:
    """Read the five analytical tables back into DataFrames."""

    engine = get_sqlite_engine(path)
    frames: Dict[str, pd.DataFrame] = {}

    for key in VIEW_KEYS:
        try:
            with engine.connect() as connection:
                frames[key] = pd.read_sql(
                    text(f'SELECT * FROM "{key}"'), connection
                )
        except Exception:
            frames[key] = _empty_frame(VIEW_COLUMNS[key])

    return frames


def ensure_sqlite_store(
    path: Optional[Path | str] = None, force: bool = False
) -> Path:
    """Create and seed the SQLite store when it is missing or empty."""

    resolved = get_sqlite_path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    if not force and resolved.exists():
        try:
            engine = get_sqlite_engine(resolved)
            with engine.connect() as connection:
                count = connection.exec_driver_sql(
                    'SELECT COUNT(*) FROM "sales_summary"'
                ).scalar()
            if count and int(count) > 0:
                with engine.begin() as connection:
                    _create_sql_views(connection)
                return resolved
        except Exception:
            # Missing tables/views: fall through and rebuild the file.
            pass

    from .sample_data import build_sample_frames
    from .transform import transform_data

    cleaned = transform_data(build_sample_frames())
    views = derive_views(cleaned)
    write_views(views, raw_frames=cleaned, path=resolved)
    logger.info("Seeded embedded SQLite analytics store at %s.", resolved)
    return resolved


def reset_sqlite_store(path: Optional[Path | str] = None) -> Path:
    """Delete the SQLite file and rebuild it from the baseline sample ETL."""

    resolved = get_sqlite_path(path).resolve()
    dispose_sqlite_engines(resolved)

    if resolved.exists():
        try:
            resolved.unlink()
        except OSError:
            # Windows may keep a handle alive briefly; drop the objects instead.
            engine = get_sqlite_engine(resolved)
            with engine.begin() as connection:
                for key in VIEW_KEYS:
                    connection.exec_driver_sql(
                        f'DROP VIEW IF EXISTS "{VIEW_SQL_NAMES[key]}"'
                    )
                for table in set(VIEW_KEYS) | set(RAW_TABLE_NAMES):
                    connection.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
            dispose_sqlite_engines(resolved)

    return ensure_sqlite_store(resolved, force=True)


# --------------------------------------------------------------------------- #
# Live order simulation
# --------------------------------------------------------------------------- #

_SIM_STATUSES = ("delivered", "shipped", "processing", "canceled", "invoiced")
_SIM_STATUS_WEIGHTS = np.array([0.82, 0.08, 0.05, 0.03, 0.02])

_SIM_PAYMENT_TYPES = ("credit_card", "pix", "boleto", "voucher", "debit_card")
_SIM_PAYMENT_WEIGHTS = np.array([0.40, 0.22, 0.18, 0.12, 0.08])

_DEFAULT_STATES = ("SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "ES", "GO")
_DEFAULT_STATE_WEIGHTS = np.array(
    [0.42, 0.13, 0.12, 0.06, 0.05, 0.04, 0.04, 0.03, 0.02, 0.02]
)
_DEFAULT_CITIES = {
    "SP": ("sao paulo", "campinas", "guarulhos", "santos"),
    "RJ": ("rio de janeiro", "niteroi", "duque de caxias"),
    "MG": ("belo horizonte", "uberlandia", "juiz de fora"),
    "RS": ("porto alegre", "caxias do sul", "pelotas"),
    "PR": ("curitiba", "londrina", "maringa"),
    "SC": ("florianopolis", "joinville", "blumenau"),
    "BA": ("salvador", "feira de santana"),
    "DF": ("brasilia",),
    "ES": ("vitoria", "vila velha"),
    "GO": ("goiania", "aparecida de goiania"),
}
_DEFAULT_CATEGORIES = (
    "bed_bath_table",
    "health_beauty",
    "sports_leisure",
    "furniture_decor",
    "computers_accessories",
    "housewares",
    "watches_gifts",
    "telephony",
    "garden_tools",
    "auto",
    "toys",
    "cool_stuff",
)


def _state_pool(sales: pd.DataFrame) -> Tuple[List[str], np.ndarray]:
    if "customer_state" in sales.columns and not sales.empty:
        counts = sales["customer_state"].dropna().astype(str).value_counts()
        if not counts.empty:
            probabilities = counts.to_numpy(dtype=float)
            return list(counts.index), probabilities / probabilities.sum()

    return list(_DEFAULT_STATES), _DEFAULT_STATE_WEIGHTS / _DEFAULT_STATE_WEIGHTS.sum()


def _city_pool(sales: pd.DataFrame) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    if {"customer_state", "customer_city"} <= set(sales.columns):
        for state, group in sales.dropna(subset=["customer_state"]).groupby(
            "customer_state"
        ):
            values = (
                group["customer_city"].dropna().astype(str).unique().tolist()
            )
            if values:
                mapping[str(state)] = values

    for state, cities in _DEFAULT_CITIES.items():
        mapping.setdefault(state, list(cities))
    return mapping


def _category_pool(products: pd.DataFrame) -> List[str]:
    if "category_name" in products.columns:
        values = products["category_name"].dropna().astype(str).unique().tolist()
        if values:
            return values
    return list(_DEFAULT_CATEGORIES)


def _payment_pool(payments: pd.DataFrame) -> Tuple[List[str], np.ndarray]:
    if "payment_type" in payments.columns and not payments.empty:
        counts = payments["payment_type"].dropna().astype(str).value_counts()
        if not counts.empty:
            probabilities = counts.to_numpy(dtype=float)
            return list(counts.index), probabilities / probabilities.sum()

    return list(_SIM_PAYMENT_TYPES), _SIM_PAYMENT_WEIGHTS / _SIM_PAYMENT_WEIGHTS.sum()


def _merge_aggregates(
    base: pd.DataFrame,
    additions: pd.DataFrame,
    group_columns: Sequence[str],
    value_columns: Sequence[str],
    output_columns: Sequence[str],
) -> pd.DataFrame:
    pieces = []
    if isinstance(base, pd.DataFrame) and not base.empty:
        pieces.append(base.loc[:, list(output_columns)].copy())
    if isinstance(additions, pd.DataFrame) and not additions.empty:
        pieces.append(additions.loc[:, list(output_columns)].copy())

    if not pieces:
        return _empty_frame(output_columns)

    combined = pd.concat(pieces, ignore_index=True)
    for column in group_columns:
        combined[column] = combined[column].astype(str)

    grouped = combined.groupby(list(group_columns), as_index=False)[
        list(value_columns)
    ].sum()
    return grouped


def simulate_orders(
    views: Dict[str, pd.DataFrame],
    count: int,
    now: Optional[Any] = None,
    seed: Optional[int] = None,
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """Append realistic synthetic orders to a set of analytical views.

    Dates are generated between the existing maximum date (or one year ago)
    and ``now``, and are clamped into 2026 or later when possible, so the
    dashboard's date axis visibly extends through 2026.
    """

    count = int(count)
    if count < 1:
        raise ValueError("count must be at least 1")

    rng = np.random.default_rng(seed)
    updated = {
        key: (
            views.get(key).copy()
            if isinstance(views.get(key), pd.DataFrame)
            else _empty_frame(columns)
        )
        for key, columns in VIEW_COLUMNS.items()
    }

    sales = updated["sales_summary"]
    customers = updated["customer_segments"]
    products = updated["product_performance"]
    payments = updated["payment_analysis"]
    reviews = updated["review_summary"]

    now_ts = (
        pd.Timestamp(now).normalize()
        if now is not None
        else pd.Timestamp.now().normalize()
    )
    sales_dates = pd.to_datetime(
        sales["order_purchase_timestamp"], errors="coerce"
    ) if "order_purchase_timestamp" in sales.columns else pd.Series(dtype="datetime64[ns]")
    latest = sales_dates.max() if not sales_dates.empty else pd.NaT

    start = now_ts - pd.Timedelta(days=365)
    if pd.notna(latest):
        start = max(start, pd.Timestamp(latest).normalize() + pd.Timedelta(days=1))
    if now_ts >= pd.Timestamp("2026-01-01"):
        start = max(start, pd.Timestamp("2026-01-01"))
    if start >= now_ts:
        start = now_ts - pd.Timedelta(days=30)

    span_seconds = max(int((now_ts - start).total_seconds()), 86_400)
    timestamps = start + pd.to_timedelta(
        rng.integers(0, span_seconds, count), unit="s"
    )
    order_ids = [f"sim_{uuid.uuid4().hex}" for _ in range(count)]

    states, state_probabilities = _state_pool(sales)
    cities_by_state = _city_pool(sales)
    chosen_states = rng.choice(states, size=count, p=state_probabilities)
    chosen_cities = [
        str(
            cities_by_state.get(str(state), _DEFAULT_CITIES["SP"])[
                int(rng.integers(0, len(cities_by_state.get(str(state), _DEFAULT_CITIES["SP"]))))
            ]
        )
        for state in chosen_states
    ]

    values = np.round(rng.gamma(shape=2.4, scale=65.0, size=count) + 9.90, 2)
    statuses = rng.choice(
        _SIM_STATUSES,
        size=count,
        p=_SIM_STATUS_WEIGHTS / _SIM_STATUS_WEIGHTS.sum(),
    )

    new_sales = pd.DataFrame(
        {
            "order_id": order_ids,
            "order_status": statuses,
            "order_purchase_timestamp": timestamps,
            "customer_state": chosen_states,
            "customer_city": chosen_cities,
            "total_order_value": values,
        }
    )

    # ---------------------------------------------------------- customers
    existing_ids: List[str] = []
    if "customer_unique_id" in customers.columns and not customers.empty:
        existing_ids = (
            customers["customer_unique_id"].dropna().astype(str).unique().tolist()
        )

    new_customer_mask = rng.random(count) < 0.62
    assigned_ids: List[str] = []
    for index in range(count):
        if new_customer_mask[index] or not existing_ids:
            assigned_ids.append(f"sim_cust_{uuid.uuid4().hex[:20]}")
        else:
            assigned_ids.append(
                existing_ids[int(rng.integers(0, len(existing_ids)))]
            )

    delta_rows = pd.DataFrame(
        {
            "customer_unique_id": assigned_ids,
            "customer_city": chosen_cities,
            "customer_state": chosen_states,
            "lifetime_orders": np.where(new_customer_mask, 1, 1),
            "lifetime_spent": values,
        }
    )
    if not customers.empty and "customer_unique_id" in customers.columns:
        base_customers = customers.copy()
        for column in ("lifetime_orders", "lifetime_spent"):
            base_customers[column] = pd.to_numeric(
                base_customers[column], errors="coerce"
            ).fillna(0)
        combined_customers = pd.concat(
            [base_customers, delta_rows], ignore_index=True
        )
        updated["customer_segments"] = (
            combined_customers.groupby("customer_unique_id", as_index=False)
            .agg(
                customer_city=("customer_city", "first"),
                customer_state=("customer_state", "first"),
                lifetime_orders=("lifetime_orders", "sum"),
                lifetime_spent=("lifetime_spent", "sum"),
            )
            .sort_values("lifetime_spent", ascending=False, ignore_index=True)
        )
        updated["customer_segments"]["lifetime_spent"] = updated[
            "customer_segments"
        ]["lifetime_spent"].round(2)
    else:
        updated["customer_segments"] = _empty_frame(
            VIEW_COLUMNS["customer_segments"]
        )

    # ----------------------------------------------------------- products
    categories = _category_pool(products)
    chosen_categories = rng.choice(categories, size=count)
    units = rng.integers(1, 4, size=count)
    sale_months = pd.Series(timestamps).dt.strftime("%Y-%m")
    new_products = pd.DataFrame(
        {
            "category_name": chosen_categories,
            "total_units_sold": units,
            "total_category_revenue": values,
            "sale_month": sale_months,
        }
    )
    product_additions = (
        new_products.groupby(["category_name", "sale_month"], as_index=False)
        .agg(
            total_units_sold=("total_units_sold", "sum"),
            total_category_revenue=("total_category_revenue", "sum"),
        )
    )
    updated["product_performance"] = _merge_aggregates(
        products,
        product_additions,
        group_columns=("category_name", "sale_month"),
        value_columns=("total_units_sold", "total_category_revenue"),
        output_columns=VIEW_COLUMNS["product_performance"],
    )
    updated["product_performance"]["total_units_sold"] = updated[
        "product_performance"
    ]["total_units_sold"].round(0).astype(int)
    updated["product_performance"]["total_category_revenue"] = updated[
        "product_performance"
    ]["total_category_revenue"].round(2)

    # ----------------------------------------------------------- payments
    payment_types, payment_probabilities = _payment_pool(payments)
    chosen_payments = rng.choice(
        payment_types, size=count, p=payment_probabilities
    )
    new_payments = pd.DataFrame(
        {
            "payment_type": chosen_payments,
            "transaction_count": 1,
            "total_volume": values,
            "average_transaction_value": values,
            "sale_month": sale_months,
        }
    )
    payment_additions = (
        new_payments.groupby(["payment_type", "sale_month"], as_index=False)
        .agg(
            transaction_count=("transaction_count", "sum"),
            total_volume=("total_volume", "sum"),
        )
    )
    payment_additions["average_transaction_value"] = (
        payment_additions["total_volume"]
        / payment_additions["transaction_count"].replace(0, np.nan)
    ).fillna(0.0)
    updated["payment_analysis"] = _merge_aggregates(
        payments,
        payment_additions,
        group_columns=("payment_type", "sale_month"),
        value_columns=("transaction_count", "total_volume"),
        output_columns=("payment_type", "sale_month", "transaction_count", "total_volume"),
    )
    updated["payment_analysis"]["average_transaction_value"] = (
        updated["payment_analysis"]["total_volume"]
        / updated["payment_analysis"]["transaction_count"].replace(0, np.nan)
    ).fillna(0.0).round(2)
    updated["payment_analysis"]["total_volume"] = updated["payment_analysis"][
        "total_volume"
    ].round(2)
    updated["payment_analysis"]["transaction_count"] = updated[
        "payment_analysis"
    ]["transaction_count"].astype(int)
    updated["payment_analysis"] = updated["payment_analysis"].loc[
        :, list(VIEW_COLUMNS["payment_analysis"])
    ]

    # ------------------------------------------------------------ reviews
    review_mask = rng.random(count) < 0.72
    review_scores = rng.choice(
        np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
        size=count,
        p=np.array([0.05, 0.05, 0.08, 0.27, 0.55]) / 1.0,
    )
    review_dates = timestamps + pd.to_timedelta(
        rng.integers(1, 15, count), unit="D"
    )
    new_reviews = pd.DataFrame(
        {
            "order_id": np.array(order_ids)[review_mask],
            "average_score": review_scores[review_mask],
            "review_count": 1,
            "review_creation_date": review_dates[review_mask],
        }
    )
    if not new_reviews.empty:
        base_reviews = reviews.loc[
            :, list(VIEW_COLUMNS["review_summary"])
        ].copy()
        base_reviews["review_creation_date"] = pd.to_datetime(
            base_reviews["review_creation_date"], errors="coerce"
        )
        new_reviews["review_creation_date"] = pd.to_datetime(
            new_reviews["review_creation_date"], errors="coerce"
        )
        updated["review_summary"] = pd.concat(
            [base_reviews, new_reviews], ignore_index=True
        ).sort_values("review_creation_date", ignore_index=True)
    else:
        updated["review_summary"] = reviews

    # -------------------------------------------------------------- sales
    base_sales = sales.loc[:, list(VIEW_COLUMNS["sales_summary"])].copy()
    base_sales["order_purchase_timestamp"] = pd.to_datetime(
        base_sales["order_purchase_timestamp"], errors="coerce"
    )
    updated["sales_summary"] = pd.concat(
        [base_sales, new_sales], ignore_index=True
    ).sort_values("order_purchase_timestamp", ignore_index=True)

    stats = {
        "orders_added": count,
        "revenue_added": round(float(new_sales["total_order_value"].sum()), 2),
        "customers_added": int(new_customer_mask.sum()),
        "reviews_added": int(review_mask.sum()),
        "window_start": str(start),
        "window_end": str(now_ts),
    }
    return updated, stats


# --------------------------------------------------------------------------- #
# Uploaded CSV ingestion
# --------------------------------------------------------------------------- #

_CANONICAL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "order_id": ("order_id", "order", "id"),
    "order_status": ("order_status", "status"),
    "order_purchase_timestamp": (
        "order_purchase_timestamp",
        "purchase_timestamp",
        "order_date",
        "purchase_date",
        "timestamp",
        "date",
    ),
    "customer_unique_id": (
        "customer_unique_id",
        "unique_id",
        "customer_id",
        "customer",
    ),
    "customer_state": ("customer_state", "state", "uf"),
    "customer_city": ("customer_city", "city", "municipality"),
    "total_order_value": (
        "total_order_value",
        "order_value",
        "payment_value",
        "total_value",
        "revenue",
        "amount",
        "price",
        "total",
        "value",
    ),
    "category_name": (
        "category_name",
        "product_category_name_english",
        "product_category",
        "category",
    ),
    "payment_type": ("payment_type", "payment_method", "payment"),
    "average_score": ("average_score", "review_score", "score", "rating"),
    "review_count": ("review_count", "reviews"),
    "review_creation_date": ("review_creation_date", "review_date"),
    "transaction_count": ("transaction_count", "transactions", "count"),
    "total_volume": ("total_volume", "volume", "total_payment_value"),
    "average_transaction_value": (
        "average_transaction_value",
        "average_value",
        "avg_value",
    ),
    "lifetime_orders": ("lifetime_orders", "orders", "order_count"),
    "lifetime_spent": (
        "lifetime_spent",
        "total_spent",
        "lifetime_value",
        "spent",
    ),
    "total_units_sold": ("total_units_sold", "units_sold", "quantity", "qty"),
    "total_category_revenue": (
        "total_category_revenue",
        "category_revenue",
        "revenue",
    ),
    "sale_month": ("sale_month", "month", "period"),
}

_VIEW_REQUIRED: Dict[str, Tuple[str, ...]] = {
    "sales_summary": (
        "order_id",
        "order_purchase_timestamp",
        "total_order_value",
    ),
    "customer_segments": ("customer_unique_id", "lifetime_spent"),
    "product_performance": (
        "category_name",
        "total_category_revenue",
    ),
    "payment_analysis": ("payment_type", "total_volume"),
    "review_summary": ("order_id", "average_score"),
}

_VOLUME_ALIASES = (
    "total_order_value",
    "payment_value",
    "price",
    "total_value",
    "revenue",
    "amount",
    "total",
    "value",
)


def normalise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase/underscore column names and apply canonical aliases."""

    frame = df.copy()
    frame.columns = [
        str(column).strip().lower().replace(" ", "_").replace("-", "_")
        for column in frame.columns
    ]
    frame = frame.loc[:, ~frame.columns.duplicated()].copy()

    for canonical, aliases in _CANONICAL_ALIASES.items():
        if canonical in frame.columns:
            continue
        for alias in aliases:
            if alias in frame.columns:
                frame = frame.rename(columns={alias: canonical})
                break

    return frame


def detect_view_key(df: pd.DataFrame) -> Optional[str]:
    """Return the analytical view whose required columns are present."""

    columns = set(df.columns)
    for key, required in _VIEW_REQUIRED.items():
        if set(required) <= columns:
            return key
    return None


def _looks_like_unified_orders(df: pd.DataFrame) -> bool:
    markers = {
        "payment_type",
        "category_name",
        "average_score",
        "customer_unique_id",
        "lifetime_spent",
    }
    return bool(markers & set(df.columns))


def _coerce_view_frame(key: str, df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()

    if key == "sales_summary":
        frame["order_purchase_timestamp"] = pd.to_datetime(
            frame["order_purchase_timestamp"], errors="coerce"
        )
        frame["total_order_value"] = _numeric(
            frame, "total_order_value"
        ).fillna(0.0).round(2)
        frame["order_status"] = _text_column(
            frame, "order_status", "delivered"
        )
        frame["customer_state"] = _text_column(
            frame, "customer_state", "unknown"
        )
        frame["customer_city"] = _text_column(
            frame, "customer_city", "unknown"
        )
        frame = frame.dropna(subset=["order_id"]).drop_duplicates("order_id")

    elif key == "customer_segments":
        frame["lifetime_orders"] = (
            _numeric(frame, "lifetime_orders").fillna(1).astype(int)
        )
        frame["lifetime_spent"] = _numeric(
            frame, "lifetime_spent"
        ).fillna(0.0).round(2)
        frame["customer_city"] = _text_column(
            frame, "customer_city", "unknown"
        )
        frame["customer_state"] = _text_column(
            frame, "customer_state", "unknown"
        )
        frame = frame.dropna(subset=["customer_unique_id"]).drop_duplicates(
            "customer_unique_id"
        )

    elif key == "product_performance":
        frame["total_units_sold"] = (
            _numeric(frame, "total_units_sold").fillna(1).round(0).astype(int)
        )
        frame["total_category_revenue"] = _numeric(
            frame, "total_category_revenue"
        ).fillna(0.0).round(2)
        frame["category_name"] = _text_column(
            frame, "category_name", "unknown"
        )
        if "sale_month" in frame.columns:
            frame["sale_month"] = _month_series(frame["sale_month"]).fillna(
                pd.Timestamp.now().strftime("%Y-%m")
            )
        else:
            frame["sale_month"] = pd.Timestamp.now().strftime("%Y-%m")

    elif key == "payment_analysis":
        frame["transaction_count"] = (
            _numeric(frame, "transaction_count").fillna(1).astype(int)
        )
        frame["total_volume"] = _numeric(
            frame, "total_volume"
        ).fillna(0.0).round(2)
        frame["average_transaction_value"] = (
            _numeric(frame, "average_transaction_value")
            .fillna(
                frame["total_volume"]
                / frame["transaction_count"].replace(0, np.nan)
            )
            .fillna(0.0)
            .round(2)
        )
        frame["payment_type"] = _text_column(
            frame, "payment_type", "not_defined"
        )
        if "sale_month" in frame.columns:
            frame["sale_month"] = _month_series(frame["sale_month"]).fillna(
                pd.Timestamp.now().strftime("%Y-%m")
            )
        else:
            frame["sale_month"] = pd.Timestamp.now().strftime("%Y-%m")

    elif key == "review_summary":
        frame["average_score"] = pd.to_numeric(
            frame["average_score"], errors="coerce"
        ).clip(0, 5)
        frame["review_count"] = (
            _numeric(frame, "review_count").fillna(1).astype(int)
        )
        if "review_creation_date" in frame.columns:
            frame["review_creation_date"] = pd.to_datetime(
                frame["review_creation_date"], errors="coerce"
            )
        else:
            frame["review_creation_date"] = pd.Timestamp.now()
        frame = frame.dropna(subset=["order_id", "average_score"])

    for column in VIEW_COLUMNS[key]:
        if column not in frame.columns:
            frame[column] = np.nan

    return frame.loc[:, list(VIEW_COLUMNS[key])].reset_index(drop=True)


def _views_from_unified_orders(df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    frame = df.copy()
    notes: List[str] = []

    if "order_id" not in frame.columns:
        raise ValueError(
            "A unified orders CSV must contain an order identifier column "
            "(order_id, order, or id)."
        )

    value_column = next(
        (column for column in _VOLUME_ALIASES if column in frame.columns), None
    )
    if value_column is None:
        raise ValueError(
            "A unified orders CSV must contain a monetary column "
            "(total_order_value, payment_value, price, revenue, ...)."
        )

    frame["_value"] = _numeric(frame, value_column).fillna(0.0)

    if "order_purchase_timestamp" in frame.columns:
        frame["_timestamp"] = pd.to_datetime(
            frame["order_purchase_timestamp"], errors="coerce"
        )
    else:
        frame["_timestamp"] = pd.Timestamp.now()
        notes.append("No date column found; all uploaded orders use today's date.")

    sales = pd.DataFrame(
        {
            "order_id": frame["order_id"].astype(str),
            "order_status": _text_column(frame, "order_status", "delivered"),
            "order_purchase_timestamp": frame["_timestamp"],
            "customer_state": _text_column(frame, "customer_state", "unknown"),
            "customer_city": _text_column(frame, "customer_city", "unknown"),
            "total_order_value": frame["_value"].round(2),
        }
    )
    sales = sales.dropna(subset=["order_id"]).drop_duplicates("order_id")
    notes.append("Derived sales_summary from the uploaded order rows.")

    if "customer_unique_id" in frame.columns:
        customer_source = frame.assign(
            _customer_key=frame["customer_unique_id"].astype(str)
        )
    else:
        customer_source = frame.assign(_customer_key=sales["order_id"])
        notes.append(
            "No customer key found; each uploaded order is treated as a "
            "separate customer."
        )

    customers = (
        customer_source.groupby("_customer_key", as_index=False)
        .agg(
            customer_city=("customer_city", "first"),
            customer_state=("customer_state", "first"),
            lifetime_orders=("order_id", "nunique"),
            lifetime_spent=("_value", "sum"),
        )
        .rename(columns={"_customer_key": "customer_unique_id"})
    )
    customers["lifetime_spent"] = customers["lifetime_spent"].round(2)
    notes.append("Derived customer_segments from order history.")

    views: Dict[str, pd.DataFrame] = {
        "sales_summary": _coerce_view_frame("sales_summary", sales),
        "customer_segments": _coerce_view_frame(
            "customer_segments", customers
        ),
    }

    if "category_name" in frame.columns:
        months = _month_series(frame["_timestamp"]).fillna(
            pd.Timestamp.now().strftime("%Y-%m")
        )
        products = (
            pd.DataFrame(
                {
                    "category_name": _text_column(
                        frame, "category_name", "unknown"
                    ),
                    "total_units_sold": 1,
                    "total_category_revenue": frame["_value"],
                    "sale_month": months,
                }
            )
            .groupby(["category_name", "sale_month"], as_index=False)
            .agg(
                total_units_sold=("total_units_sold", "sum"),
                total_category_revenue=("total_category_revenue", "sum"),
            )
        )
        views["product_performance"] = _coerce_view_frame(
            "product_performance", products
        )
        notes.append("Derived product_performance from the category column.")
    else:
        notes.append(
            "No category column found; product_performance keeps the current "
            "live data."
        )

    if "payment_type" in frame.columns:
        months = _month_series(frame["_timestamp"]).fillna(
            pd.Timestamp.now().strftime("%Y-%m")
        )
        payments = (
            pd.DataFrame(
                {
                    "payment_type": _text_column(
                        frame, "payment_type", "not_defined"
                    ),
                    "transaction_count": 1,
                    "total_volume": frame["_value"],
                    "sale_month": months,
                }
            )
            .groupby(["payment_type", "sale_month"], as_index=False)
            .agg(
                transaction_count=("transaction_count", "sum"),
                total_volume=("total_volume", "sum"),
            )
        )
        payments["average_transaction_value"] = (
            payments["total_volume"]
            / payments["transaction_count"].replace(0, np.nan)
        ).fillna(0.0)
        views["payment_analysis"] = _coerce_view_frame(
            "payment_analysis", payments
        )
        notes.append("Derived payment_analysis from the payment column.")
    else:
        notes.append(
            "No payment column found; payment_analysis keeps the current live "
            "data."
        )

    if "average_score" in frame.columns:
        reviews = (
            pd.DataFrame(
                {
                    "order_id": frame["order_id"].astype(str),
                    "average_score": pd.to_numeric(
                        frame["average_score"], errors="coerce"
                    ),
                    "review_count": 1,
                    "review_creation_date": frame["_timestamp"],
                }
            )
            .dropna(subset=["average_score"])
        )
        if not reviews.empty:
            views["review_summary"] = _coerce_view_frame(
                "review_summary", reviews
            )
            notes.append("Derived review_summary from the review score column.")
        else:
            notes.append("Review scores could not be parsed; reviews are unchanged.")
    else:
        notes.append(
            "No review score column found; review_summary keeps the current "
            "live data."
        )

    return views, notes


def views_from_dataframe(
    df: pd.DataFrame, view_key: Optional[str] = None
) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """Translate an uploaded CSV into one or more analytical views."""

    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("The uploaded CSV contains no rows.")

    frame = normalise_dataframe(df)

    if view_key:
        if view_key not in VIEW_KEYS:
            raise ValueError(f"Unknown dashboard view: {view_key}")
        missing = [
            column
            for column in _VIEW_REQUIRED[view_key]
            if column not in frame.columns
        ]
        if missing:
            raise ValueError(
                f"{view_key} requires the columns: {', '.join(missing)}."
            )
        return {
            view_key: _coerce_view_frame(view_key, frame)
        }, [f"Loaded a {view_key} CSV with {len(frame):,} rows."]

    if _looks_like_unified_orders(frame):
        return _views_from_unified_orders(frame)

    detected = detect_view_key(frame)
    if detected is not None:
        return {
            detected: _coerce_view_frame(detected, frame)
        }, [f"Detected a {detected} CSV with {len(frame):,} rows."]

    return _views_from_unified_orders(frame)
