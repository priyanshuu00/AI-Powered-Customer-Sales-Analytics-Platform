import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataProfiler:
    def __init__(self):
        load_dotenv()
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "3306")
        DB_NAME = os.getenv("DB_NAME", "olist_analytics")
        self.db_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        self.engine = create_engine(self.db_uri)

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
            "data_types": df.dtypes.astype(str).to_dict()
        }
        return profile
