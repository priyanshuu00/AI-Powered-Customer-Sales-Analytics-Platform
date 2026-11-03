"""Exploratory data profiling against the MySQL warehouse.

The engine comes from :func:`database.db_connection.get_db_engine`, which builds
the DSN through ``sqlalchemy.engine.URL.create``. Credentials are therefore
percent-encoded, so a password containing ``@`` or ``:`` no longer breaks the
connection string.
"""

import logging

import pandas as pd

from database.db_connection import get_db_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DataProfiler:
    def __init__(self):
        self.engine = get_db_engine()

    def load_table(self, table_name: str) -> pd.DataFrame:
        query = f"SELECT * FROM {table_name}"
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            logger.error(f"Failed to load table {table_name}: {e}")
            return pd.DataFrame()

    def profile_data(self, df: pd.DataFrame, table_name: str) -> dict:
        if df.empty:
            return {}
        profile = {
            "table": table_name,
            "shape": df.shape,
            "columns": list(df.columns),
            "missing_values": df.isnull().sum().to_dict(),
            "duplicate_count": int(df.duplicated().sum()),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
            "data_types": df.dtypes.astype(str).to_dict(),
        }
        return profile
