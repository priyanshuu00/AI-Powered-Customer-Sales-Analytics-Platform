"""ETL configuration and path resolution."""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

DEFAULT_DB_NAME = "sales_analytics_db"

# Database Config
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", DEFAULT_DB_NAME)

DB_URI = URL.create(
    drivername="mysql+mysqlconnector",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT) if str(DB_PORT).isdigit() else 3306,
    database=DB_NAME,
)

# File Paths: prefer data/raw/, fall back to the legacy data/ layout.
BASE_DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = BASE_DATA_DIR / "raw"


def resolve_csv_path(filename: str) -> str:
    """Resolve a dataset CSV, checking ``data/raw`` before the legacy root."""

    raw_path = RAW_DATA_DIR / filename
    if raw_path.exists():
        return str(raw_path)

    legacy_path = BASE_DATA_DIR / filename
    if legacy_path.exists():
        return str(legacy_path)

    # Canonical location for error messages when neither file exists.
    return str(raw_path)


FILE_PATHS = {
    "geolocation": resolve_csv_path("olist_geolocation_dataset.csv"),
    "customers": resolve_csv_path("olist_customers_dataset.csv"),
    "sellers": resolve_csv_path("olist_sellers_dataset.csv"),
    "products": resolve_csv_path("olist_products_dataset.csv"),
    "category_translation": resolve_csv_path(
        "product_category_name_translation.csv"
    ),
    "orders": resolve_csv_path("olist_orders_dataset.csv"),
    "order_items": resolve_csv_path("olist_order_items_dataset.csv"),
    "payments": resolve_csv_path("olist_payments_dataset.csv"),
    "reviews": resolve_csv_path("olist_reviews_dataset.csv"),
}

# Ensure reports directory exists
REPORTS_DIR = str(PROJECT_ROOT / "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Logging Configuration
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(REPORTS_DIR, "etl_pipeline.log"),
                mode='w',
                encoding='utf-8',
            )
        ]
    )
    return logging.getLogger("ETL_Pipeline")


logger = setup_logging()
