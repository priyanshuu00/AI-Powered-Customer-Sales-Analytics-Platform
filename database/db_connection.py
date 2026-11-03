"""Database Module - Connection Handler.

Manages SQLAlchemy engine creation and the MySQL connection lifecycle.
The ``.env`` file is always resolved relative to the repository root, and
credentials are passed through ``URL.create`` so special characters (``@``,
``:``) are percent-encoded correctly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

DEFAULT_DB_NAME = "sales_analytics_db"


class DatabaseConnector:
    """Manages the database connection pool and engine instantiation."""

    def __init__(self) -> None:
        self.host: str = os.getenv("DB_HOST", "localhost")
        try:
            self.port: int = int(os.getenv("DB_PORT", "3306"))
        except (TypeError, ValueError):
            self.port = 3306
        self.user: str = os.getenv("DB_USER", "root")
        self.password: str = os.getenv("DB_PASSWORD", "")
        self.database: str = os.getenv("DB_NAME", DEFAULT_DB_NAME)
        self._engine: Optional[Engine] = None

    def get_connection_url(self) -> URL:
        """Construct a SQLAlchemy URL with safely encoded credentials."""

        return URL.create(
            drivername="mysql+mysqlconnector",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )

    def get_engine(self) -> Engine:
        """Initialize and return a pooled SQLAlchemy engine."""

        if self._engine is None:
            self._engine = create_engine(
                self.get_connection_url(),
                pool_pre_ping=True,
                pool_recycle=1800,
                connect_args={"connect_timeout": 3},
            )
        return self._engine


_DEFAULT_CONNECTOR: Optional[DatabaseConnector] = None


def get_db_engine() -> Engine:
    """Return the shared, lazily-created engine for the configured database.

    Callers in ``analysis/`` and scripts should use this instead of building a
    DSN string by hand: ``URL.create`` percent-encodes credentials, so a
    password containing ``@``, ``:`` or ``/`` cannot corrupt the URL.
    """

    global _DEFAULT_CONNECTOR
    if _DEFAULT_CONNECTOR is None:
        _DEFAULT_CONNECTOR = DatabaseConnector()
    return _DEFAULT_CONNECTOR.get_engine()
