"""Load transformed ETL frames into the active analytics warehouse.

MySQL remains the preferred target. When it is unreachable (the normal case
for a cloud deployment without an external database), the loader falls back
to the embedded SQLite store, where it writes the raw tables *and* derives
the five analytical dashboard views.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from .config import DB_URI, logger

# Foreign-key-safe insertion order.
LOAD_ORDER = (
    "geolocation",
    "category_translation",
    "customers",
    "sellers",
    "products",
    "orders",
    "order_items",
    "payments",
    "reviews",
)


def _load_to_mysql(dfs: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """Write frames into MySQL. Raises when the server/schema is unavailable."""

    engine = create_engine(
        DB_URI,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )

    # Fail fast when the server is unreachable before opening a transaction.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    load_stats: Dict[str, int] = {}

    with engine.begin() as connection:
        for table_name in LOAD_ORDER:
            frame = dfs.get(table_name)
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                logger.info("Loading table %s into MySQL...", table_name)
                frame.to_sql(
                    name=table_name,
                    con=connection,
                    if_exists="append",
                    index=False,
                    chunksize=10000,
                )
                load_stats[table_name] = int(len(frame))
                logger.info("Loaded %d rows into %s.", len(frame), table_name)
            else:
                logger.warning(
                    "Table %s has no data to load or was not extracted.",
                    table_name,
                )
                load_stats[table_name] = 0

    return load_stats


def _load_to_sqlite(dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Write raw tables plus derived analytical views into embedded SQLite."""

    from .sqlite_store import derive_views, get_sqlite_path, write_views

    views = derive_views(dfs)
    path = get_sqlite_path()
    write_views(views, raw_frames=dfs, path=path)

    table_stats = {
        name: int(len(dfs[name]))
        for name in LOAD_ORDER
        if isinstance(dfs.get(name), pd.DataFrame)
    }
    view_stats = {key: int(len(frame)) for key, frame in views.items()}

    logger.info(
        "Loaded %d raw tables and %d analytical views into SQLite at %s.",
        len(table_stats),
        len(view_stats),
        path,
    )
    return {
        "target": "sqlite",
        "tables": table_stats,
        "views": view_stats,
        "path": str(path),
    }


def load_data(
    dfs: Dict[str, pd.DataFrame], target: Optional[str] = None
) -> Dict[str, Any]:
    """Load frames into MySQL, falling back to embedded SQLite.

    Parameters
    ----------
    dfs:
        Transformed ETL frames.
    target:
        ``"mysql"``, ``"sqlite"``, or ``None`` (prefer MySQL, fall back).

    Returns
    -------
    A structured result with the target, per-table row counts, derived view
    row counts, and the SQLite path when applicable.
    """

    logger.info("Loading started (target=%s).", target or "auto")

    if target not in (None, "mysql", "sqlite"):
        raise ValueError(f"Unknown load target: {target!r}")

    fallback_reason: Optional[str] = None

    if target in (None, "mysql"):
        try:
            stats = _load_to_mysql(dfs)
            logger.info("Loading completed successfully into MySQL.")
            return {
                "target": "mysql",
                "tables": stats,
                "views": {},
                "path": None,
                "fallback_reason": None,
            }
        except Exception as exc:
            fallback_reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "MySQL load unavailable (%s); falling back to embedded SQLite.",
                fallback_reason,
            )
            if target == "mysql":
                raise

    result = _load_to_sqlite(dfs)
    if fallback_reason:
        result["fallback_reason"] = fallback_reason
    logger.info("Loading completed successfully into %s.", result["target"])
    return result
