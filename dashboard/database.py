"""Database access layer for the Streamlit dashboard.

The dashboard resolves data through three tiers:

1. ``live_mysql`` — a reachable MySQL warehouse exposing the five ``vw_*``
   analytical views.
2. ``live_sqlite`` — an embedded, persistent SQLAlchemy/SQLite database at
   ``data/processed/analytics_live.db``. It is auto-seeded on first run from
   the ETL sample generator and holds real tables plus real SQL views.
3. ``session_override`` — ``st.session_state["custom_views"]``, populated by
   uploaded CSVs or the live order simulator. It overrides every tier in
   real time.

The deterministic synthetic dataset is kept only as a last-resort guard when
both database engines are unavailable; normal cloud deployments always land
on the ``live_sqlite`` tier.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from etl import sqlite_store

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# --------------------------------------------------------------------------- #
# Connection configuration
# --------------------------------------------------------------------------- #

DEFAULT_DB_NAME = "sales_analytics_db"

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", DEFAULT_DB_NAME)

try:
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
except (TypeError, ValueError):
    DB_PORT = 3306

CONNECT_TIMEOUT_SECONDS = 3
MYSQL_RECHECK_SECONDS = 300
DEMO_RETRY_SECONDS = 300

# Data-source modes.
LIVE_MYSQL = "live_mysql"
LIVE_SQLITE = "live_sqlite"
SESSION_OVERRIDE = "session_override"
DEMO = "demo"
UNKNOWN = "unknown"

SOURCE_LABELS: Dict[str, str] = {
    LIVE_MYSQL: "LIVE - MYSQL WAREHOUSE",
    LIVE_SQLITE: "LIVE - CLOUD SQL ENGINE",
    SESSION_OVERRIDE: "LIVE - CUSTOM DATA",
    DEMO: "DEMO - SYNTHETIC",
    UNKNOWN: "CONNECTING",
}

# CSS classes already defined in assets/style.css.
SOURCE_CLASSES: Dict[str, str] = {
    LIVE_MYSQL: "live",
    LIVE_SQLITE: "live",
    SESSION_OVERRIDE: "live",
    DEMO: "demo",
    UNKNOWN: "connecting",
}

LIVE_VIEWS = (
    "vw_sales_summary",
    "vw_customer_summary",
    "vw_category_performance",
    "vw_payment_summary",
    "vw_review_summary",
)

# Logical demo names -> accepted SQL identifiers.
DEMO_VIEW_ALIASES: Dict[str, tuple[str, ...]] = {
    "sales_summary": ("sales_summary", "vw_sales_summary"),
    "customer_segments": ("customer_segments", "vw_customer_summary"),
    "product_performance": ("product_performance", "vw_category_performance"),
    "payment_analysis": ("payment_analysis", "vw_payment_summary"),
    "review_summary": ("review_summary", "vw_review_summary"),
}

CUSTOM_VIEWS_KEY = "custom_views"

_STATUS_KEY = "_data_source_status"
_STATUS_FALLBACK: Dict[str, Any] = {
    "mode": UNKNOWN,
    "message": "Connecting to the analytics database...",
    "since": 0.0,
    "detail": None,
}

_DEMO_CACHE: Optional[Dict[str, pd.DataFrame]] = None
_CUSTOM_VIEWS_FALLBACK: Dict[str, pd.DataFrame] = {}

_VIEW_PROBE_SQL = (
    "SELECT COUNT(*) FROM information_schema.views "
    "WHERE table_schema = DATABASE() AND table_name IN ("
    + ", ".join(f"'{view}'" for view in LIVE_VIEWS)
    + ")"
)


def build_db_url() -> URL:
    """Build a SQLAlchemy URL without string interpolation.

    ``URL.create`` percent-encodes credentials, so passwords containing
    ``@``, ``:``, ``/`` or ``#`` can no longer corrupt the hostname.
    """

    return URL.create(
        drivername="mysql+mysqlconnector",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )


@st.cache_resource(show_spinner=False)
def get_engine():
    """Create (and cache) the MySQL SQLAlchemy engine."""

    return create_engine(
        build_db_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def _mysql_signature() -> str:
    return f"{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --------------------------------------------------------------------------- #
# Session-state helpers (work with or without a Streamlit runtime)
# --------------------------------------------------------------------------- #


def _session_state():
    try:
        return st.session_state
    except Exception:  # pragma: no cover - bare/script mode
        return None


def _get_status() -> Dict[str, Any]:
    state = _session_state()
    if state is not None:
        try:
            status = state.get(_STATUS_KEY)
            if isinstance(status, dict):
                return status
        except Exception:  # pragma: no cover - bare/script mode
            pass
    return dict(_STATUS_FALLBACK)


def _set_status(mode: str, message: str, detail: Optional[str] = None) -> None:
    status = {
        "mode": mode,
        "message": message,
        "since": time.time(),
        "detail": detail,
    }
    _STATUS_FALLBACK.update(status)

    state = _session_state()
    if state is not None:
        try:
            state[_STATUS_KEY] = status
        except Exception:  # pragma: no cover - bare/script mode
            pass


def get_data_source_status() -> Dict[str, Any]:
    """Return the active tier: ``live_mysql``, ``live_sqlite``, etc."""

    return dict(_get_status())


def get_source_label(mode: Optional[str] = None) -> str:
    """Human-readable badge label for a data-source mode."""

    resolved = mode or _get_status().get("mode", UNKNOWN)
    return SOURCE_LABELS.get(resolved, str(resolved).replace("_", " ").title())


def get_source_class(mode: Optional[str] = None) -> str:
    """CSS class for a data-source mode."""

    resolved = mode or _get_status().get("mode", UNKNOWN)
    return SOURCE_CLASSES.get(resolved, "connecting")


# --------------------------------------------------------------------------- #
# Custom view overrides (Tier 3)
# --------------------------------------------------------------------------- #


def _copies(views: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    return {
        key: frame.copy()
        for key, frame in views.items()
        if key in sqlite_store.VIEW_KEYS and isinstance(frame, pd.DataFrame)
    }


def get_custom_views() -> Dict[str, pd.DataFrame]:
    """Return the session override frames (empty when none are active)."""

    state = _session_state()
    if state is not None:
        try:
            stored = state.get(CUSTOM_VIEWS_KEY)
        except Exception:  # pragma: no cover - bare/script mode
            stored = None
        if isinstance(stored, dict) and stored:
            return _copies(stored)

    return _copies(_CUSTOM_VIEWS_FALLBACK)


def has_custom_views() -> bool:
    return bool(get_custom_views())


def clear_custom_views() -> None:
    """Remove any uploaded/simulated override and fall back to the database."""

    state = _session_state()
    if state is not None:
        try:
            state.pop(CUSTOM_VIEWS_KEY, None)
        except Exception:  # pragma: no cover - bare/script mode
            pass
    _CUSTOM_VIEWS_FALLBACK.clear()

    if _get_status().get("mode") == SESSION_OVERRIDE:
        _set_status(UNKNOWN, "Custom data cleared; reconnecting to the database...")


def set_custom_views(
    views: Dict[str, pd.DataFrame],
    merge: bool = True,
    message: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Store override frames in session state (and a process-level fallback).

    ``merge=True`` keeps the other dashboard views intact, which is what a
    single-view CSV upload needs. ``merge=False`` replaces the full tier.
    """

    payload: Dict[str, pd.DataFrame] = {}
    if merge:
        base = get_custom_views()
        if not base:
            base = get_active_views()
        payload.update(_copies(base))

    payload.update(_copies(views))
    if not payload:
        raise ValueError("No recognised dashboard views were supplied.")

    state = _session_state()
    if state is not None:
        try:
            state[CUSTOM_VIEWS_KEY] = payload
        except Exception:  # pragma: no cover - bare/script mode
            _CUSTOM_VIEWS_FALLBACK.clear()
            _CUSTOM_VIEWS_FALLBACK.update(payload)
    else:
        _CUSTOM_VIEWS_FALLBACK.clear()
        _CUSTOM_VIEWS_FALLBACK.update(payload)

    _set_status(
        SESSION_OVERRIDE,
        message or "Custom data is driving every dashboard view in real time.",
    )

    try:
        st.cache_data.clear()
    except Exception:  # pragma: no cover - cache backend unavailable
        pass

    return payload


# --------------------------------------------------------------------------- #
# Data-source probing
# --------------------------------------------------------------------------- #


def _probe_mysql() -> int:
    """Return how many of the five live views MySQL exposes."""

    engine = get_engine()
    with engine.connect() as connection:
        found = connection.execute(text(_VIEW_PROBE_SQL)).scalar() or 0
    return int(found)


def _ensure_data_source() -> str:
    """Resolve the active tier, probing MySQL then the SQLite store."""

    if has_custom_views():
        if _get_status().get("mode") != SESSION_OVERRIDE:
            _set_status(
                SESSION_OVERRIDE,
                "Uploaded/simulated data is overriding the database views.",
            )
        return SESSION_OVERRIDE

    status = _get_status()
    mode = status.get("mode", UNKNOWN)
    now = time.time()

    if mode == LIVE_MYSQL:
        return LIVE_MYSQL

    if mode == LIVE_SQLITE:
        age = now - float(status.get("since") or 0.0)
        if age < MYSQL_RECHECK_SECONDS:
            return LIVE_SQLITE

    mysql_detail: Optional[str] = None
    try:
        found = _probe_mysql()
        if found == len(LIVE_VIEWS):
            _set_status(
                LIVE_MYSQL,
                f"Connected to MySQL at {DB_HOST}:{DB_PORT}/{DB_NAME}; "
                "showing live warehouse data.",
            )
            return LIVE_MYSQL
        mysql_detail = (
            f"MySQL reachable but only {found}/{len(LIVE_VIEWS)} analytics "
            "views were found."
        )
    except Exception as exc:
        mysql_detail = f"MySQL unavailable ({type(exc).__name__}: {exc})."

    try:
        path = sqlite_store.ensure_sqlite_store()
        _set_status(
            LIVE_SQLITE,
            f"Embedded SQLite engine active at {path}; showing live data.",
            detail=mysql_detail,
        )
        return LIVE_SQLITE
    except Exception as exc:
        _set_status(
            DEMO,
            "Both MySQL and the embedded SQLite engine are unavailable; "
            "showing deterministic demo data.",
            detail=f"{mysql_detail or ''} SQLite: {type(exc).__name__}: {exc}",
        )
        return DEMO


def reset_data_source() -> None:
    """Forget cached query results and force a fresh tier probe."""

    try:
        st.cache_data.clear()
    except Exception:  # pragma: no cover - bare/script mode
        pass
    try:
        get_engine.clear()
    except Exception:  # pragma: no cover - cache backend unavailable
        pass

    if not has_custom_views():
        _set_status(UNKNOWN, "Re-probing MySQL and the embedded SQLite engine...")


def reset_to_baseline() -> bool:
    """Restore the clean baseline dataset (deterministic ETL sample)."""

    clear_custom_views()
    try:
        st.cache_data.clear()
    except Exception:  # pragma: no cover - bare/script mode
        pass

    try:
        path = sqlite_store.reset_sqlite_store()
    except Exception as exc:
        _set_status(
            DEMO,
            "Could not rebuild the baseline SQLite dataset; showing demo data.",
            detail=f"{type(exc).__name__}: {exc}",
        )
        return False

    _set_status(
        UNKNOWN,
        f"Baseline dataset restored at {path}; reconnecting...",
    )
    try:
        st.cache_data.clear()
    except Exception:  # pragma: no cover - bare/script mode
        pass
    return True


# --------------------------------------------------------------------------- #
# Query execution
# --------------------------------------------------------------------------- #


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_mysql_query(query: str, signature: str) -> pd.DataFrame:
    """Run a live MySQL query. Empty results raise, so they are never cached."""

    del signature  # part of the cache key only
    engine = get_engine()
    with engine.connect() as connection:
        frame = pd.read_sql(text(query), connection)

    if frame is None or frame.empty:
        raise ValueError("Query returned no rows")
    return frame


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_sqlite_query(query: str, db_path: str) -> pd.DataFrame:
    """Run a query against the embedded SQLite engine."""

    engine = sqlite_store.get_sqlite_engine(db_path)
    with engine.connect() as connection:
        frame = pd.read_sql(text(query), connection)

    if frame is None:
        raise ValueError("Query returned no rows")
    return frame


def _resolve_view_key(query: str) -> Optional[str]:
    haystack = (query or "").lower()
    for key, aliases in DEMO_VIEW_ALIASES.items():
        if any(alias.lower() in haystack for alias in aliases):
            return key
    return None


# Backwards-compatible alias used by older call sites.
_resolve_demo_key = _resolve_view_key


def _demo_frame(key: Optional[str]) -> pd.DataFrame:
    if key is None:
        return pd.DataFrame()
    return generate_demo_views().get(key, pd.DataFrame()).copy()


def get_active_views() -> Dict[str, pd.DataFrame]:
    """Return all five views from the active tier (ignoring session state)."""

    custom = get_custom_views()
    if custom:
        return {key: custom.get(key, pd.DataFrame()).copy() for key in sqlite_store.VIEW_KEYS}

    mode = _ensure_data_source()

    if mode == LIVE_MYSQL:
        try:
            return {
                key: _cached_mysql_query(
                    sqlite_store.VIEW_QUERIES[key], _mysql_signature()
                ).copy()
                for key in sqlite_store.VIEW_KEYS
            }
        except Exception as exc:
            _set_status(
                LIVE_SQLITE,
                "A live MySQL query failed; switched to the embedded SQLite engine.",
                detail=f"{type(exc).__name__}: {exc}",
            )

    try:
        path = sqlite_store.ensure_sqlite_store()
        return sqlite_store.read_sqlite_views(path)
    except Exception:
        return generate_demo_views()


def load_data(query: str) -> pd.DataFrame:
    """Load a dashboard view from the highest-priority available tier."""

    key = _resolve_view_key(query)

    custom = get_custom_views()
    if key is not None and key in custom:
        return custom[key].copy()

    mode = _ensure_data_source()

    if mode == LIVE_MYSQL:
        try:
            return _cached_mysql_query(query, _mysql_signature()).copy()
        except Exception as exc:
            _set_status(
                LIVE_SQLITE,
                "A live MySQL query failed; switched to the embedded SQLite engine.",
                detail=f"{type(exc).__name__}: {exc}",
            )

    try:
        path = sqlite_store.ensure_sqlite_store()
        return _cached_sqlite_query(query, str(path)).copy()
    except Exception as exc:
        _set_status(
            DEMO,
            "A database query failed; showing deterministic demo data.",
            detail=f"{type(exc).__name__}: {exc}",
        )
        return _demo_frame(key)


# --------------------------------------------------------------------------- #
# Dynamic actions
# --------------------------------------------------------------------------- #


def simulate_new_orders(count: int) -> Dict[str, Any]:
    """Append realistic orders to the active tier and refresh every view."""

    views = get_active_views()
    updated, stats = sqlite_store.simulate_orders(views, count)

    mode = _get_status().get("mode", UNKNOWN)
    if has_custom_views() or mode == LIVE_MYSQL:
        # Never write synthetic rows into a real warehouse: materialise the
        # result as a session override instead.
        set_custom_views(
            updated,
            merge=False,
            message=(
                f"{stats['orders_added']:,} simulated orders appended to the "
                "session override."
            ),
        )
        stats["target"] = "session"
        return stats

    path = sqlite_store.ensure_sqlite_store()
    sqlite_store.write_views(updated, path=path)
    try:
        st.cache_data.clear()
    except Exception:  # pragma: no cover - bare/script mode
        pass

    _set_status(
        LIVE_SQLITE,
        f"{stats['orders_added']:,} simulated orders appended to the embedded "
        f"SQLite engine at {path}.",
    )
    stats["target"] = "sqlite"
    return stats


def apply_custom_views_from_frame(
    df: pd.DataFrame,
    view_key: Optional[str] = None,
    source_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply an uploaded CSV to the live dashboard via the session tier."""

    views, notes = sqlite_store.views_from_dataframe(df, view_key=view_key)
    payload = set_custom_views(
        views,
        merge=True,
        message=(
            f"Uploaded data from {source_name or 'CSV'} is driving the dashboard."
        ),
    )

    return {
        "mode": SESSION_OVERRIDE,
        "views": list(views),
        "rows": {key: int(len(frame)) for key, frame in views.items()},
        "total_rows": int(sum(len(frame) for frame in views.values())),
        "notes": notes,
        "source": source_name or "uploaded CSV",
        "available_views": sorted(payload),
    }


# --------------------------------------------------------------------------- #
# Deterministic demo data (last-resort guard)
# --------------------------------------------------------------------------- #

_CATEGORIES = (
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
    "perfumery",
    "baby",
    "electronics",
    "stationery",
    "fashion_bags_accessories",
    "consoles_games",
    "office_furniture",
    "musical_instruments",
    "construction_tools_construction",
    "food",
    "drinks",
    "pet_shop",
)

_STATE_WEIGHTS = {
    "SP": 0.42,
    "RJ": 0.13,
    "MG": 0.12,
    "RS": 0.06,
    "PR": 0.05,
    "SC": 0.04,
    "BA": 0.04,
    "DF": 0.03,
    "ES": 0.02,
    "GO": 0.02,
}

_CITIES = {
    "SP": ("sao paulo", "campinas", "guarulhos", "santos", "ribeirao preto"),
    "RJ": ("rio de janeiro", "niteroi", "duque de caxias"),
    "MG": ("belo horizonte", "uberlandia", "juiz de fora"),
    "RS": ("porto alegre", "caxias do sul", "pelotas"),
    "PR": ("curitiba", "londrina", "maringa"),
    "SC": ("florianopolis", "joinville", "blumenau"),
    "BA": ("salvador", "feira de santana", "vitoria da conquista"),
    "DF": ("brasilia",),
    "ES": ("vitoria", "vila velha", "serra"),
    "GO": ("goiania", "aparecida de goiania"),
}

_PAYMENT_TYPES = (
    ("credit_card", 520.0, 128.0),
    ("boleto", 190.0, 145.0),
    ("voucher", 90.0, 62.0),
    ("debit_card", 55.0, 112.0),
    ("pix", 140.0, 98.0),
    ("not_defined", 5.0, 75.0),
)

_ORDER_STATUS = ("delivered", "shipped", "processing", "canceled", "invoiced")
_ORDER_STATUS_WEIGHTS = (0.86, 0.05, 0.04, 0.03, 0.02)


def _random_states(rng: np.random.Generator, size: int) -> np.ndarray:
    states = list(_STATE_WEIGHTS)
    probabilities = np.array([_STATE_WEIGHTS[state] for state in states], dtype=float)
    probabilities = probabilities / probabilities.sum()
    return rng.choice(states, size=size, p=probabilities)


def _pick_city(rng: np.random.Generator, state: str) -> str:
    cities = _CITIES.get(state, ("unknown",))
    return str(cities[int(rng.integers(0, len(cities)))])


def _build_demo_views() -> Dict[str, pd.DataFrame]:
    """Generate deterministic, realistic frames for all dashboard views."""

    rng = np.random.default_rng(42)

    # ------------------------------------------------------------------ sales
    n_sales = 320
    sale_states = _random_states(rng, n_sales)
    sale_cities = [_pick_city(rng, state) for state in sale_states]
    sale_dates = (
        pd.Timestamp("2023-01-01")
        + pd.to_timedelta(rng.integers(0, 1035, n_sales), unit="D")
        + pd.to_timedelta(rng.integers(0, 86_400, n_sales), unit="s")
    )

    sales = pd.DataFrame(
        {
            "order_id": [f"{index:032x}" for index in range(1, n_sales + 1)],
            "order_status": rng.choice(
                _ORDER_STATUS, size=n_sales, p=_ORDER_STATUS_WEIGHTS
            ),
            "order_purchase_timestamp": sale_dates,
            "customer_state": sale_states,
            "customer_city": sale_cities,
            "total_order_value": np.round(
                rng.gamma(shape=2.4, scale=65.0, size=n_sales) + 9.90, 2
            ),
        }
    ).sort_values("order_purchase_timestamp", ignore_index=True)

    # -------------------------------------------------------------- customers
    n_customers = 240
    customer_states = _random_states(rng, n_customers)
    customer_cities = [_pick_city(rng, state) for state in customer_states]
    lifetime_orders = rng.integers(1, 13, n_customers)
    average_ticket = rng.gamma(shape=2.0, scale=55.0, size=n_customers) + 12.0

    customers = pd.DataFrame(
        {
            "customer_unique_id": [
                f"{0x100000 + index:032x}" for index in range(n_customers)
            ],
            "customer_city": customer_cities,
            "customer_state": customer_states,
            "lifetime_orders": lifetime_orders,
            "lifetime_spent": np.round(lifetime_orders * average_ticket, 2),
        }
    ).sort_values("lifetime_spent", ascending=False, ignore_index=True)

    # ---------------------------------------------------------------- products
    # Monthly rows are aggregated by the dashboard, mirroring the live view.
    product_months = [f"2024-{month:02d}" for month in range(1, 13)]
    product_rows = []
    for category in _CATEGORIES:
        unit_price = float(rng.uniform(25.0, 420.0))
        for month_index, month in enumerate(product_months):
            seasonality = 1.0 + 0.22 * np.sin((month_index / 12.0) * 2.0 * np.pi)
            units = int(max(5, rng.integers(40, 320) * seasonality))
            product_rows.append(
                {
                    "category_name": category,
                    "total_units_sold": units,
                    "total_category_revenue": round(units * unit_price, 2),
                    "sale_month": month,
                }
            )
    products = pd.DataFrame(product_rows)

    # ---------------------------------------------------------------- payments
    payment_months = (
        pd.date_range("2023-01-01", periods=34, freq="MS").strftime("%Y-%m").tolist()
    )
    payment_rows = []
    for type_index, (payment_type, base_count, average_ticket) in enumerate(
        _PAYMENT_TYPES
    ):
        for month_index, month in enumerate(payment_months):
            seasonality = 1.0 + 0.18 * np.cos(
                ((month_index + type_index) / 12.0) * 2.0 * np.pi
            )
            count = int(max(3, base_count * seasonality * rng.uniform(0.75, 1.25)))
            ticket = average_ticket * float(rng.uniform(0.88, 1.12))
            volume = round(count * ticket, 2)
            payment_rows.append(
                {
                    "payment_type": payment_type,
                    "transaction_count": count,
                    "total_volume": volume,
                    "average_transaction_value": round(volume / count, 2),
                    "sale_month": month,
                }
            )
    payments = pd.DataFrame(payment_rows)

    # ----------------------------------------------------------------- reviews
    n_reviews = 260
    review_order_ids = rng.choice(sales["order_id"].to_numpy(), n_reviews, replace=False)
    review_dates = (
        pd.to_datetime(
            sales.set_index("order_id").loc[
                review_order_ids, "order_purchase_timestamp"
            ]
        ).to_numpy()
        + pd.to_timedelta(rng.integers(2, 21, n_reviews), unit="D")
    )
    # Keep reviews inside the sales window so the default date filter does not
    # hide rows on first load.
    max_sale_date = sales["order_purchase_timestamp"].max()
    review_dates = pd.Series(review_dates).clip(upper=max_sale_date).to_numpy()
    score_choices = np.array([1.0, 2.0, 3.0, 3.5, 4.0, 4.5, 5.0])
    score_weights = np.array([0.06, 0.05, 0.07, 0.09, 0.20, 0.15, 0.38])
    score_weights = score_weights / score_weights.sum()

    reviews = pd.DataFrame(
        {
            "order_id": review_order_ids,
            "average_score": rng.choice(score_choices, size=n_reviews, p=score_weights),
            "review_count": rng.integers(1, 4, n_reviews),
            "review_creation_date": review_dates,
        }
    ).sort_values("review_creation_date", ignore_index=True)

    return {
        "sales_summary": sales,
        "customer_segments": customers,
        "product_performance": products,
        "payment_analysis": payments,
        "review_summary": reviews,
    }


def generate_demo_views() -> Dict[str, pd.DataFrame]:
    """Return all demo views. Deterministic across runs and safe to mutate.

    Callers receive copies, so widget code cannot corrupt the cache.
    """

    global _DEMO_CACHE
    if _DEMO_CACHE is None:
        _DEMO_CACHE = _build_demo_views()
    return {name: frame.copy() for name, frame in _DEMO_CACHE.items()}
