import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Database Config
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "olist_analytics")

DB_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# File Paths (Assuming datasets are placed in data/)
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

FILE_PATHS = {
    "geolocation": os.path.join(BASE_DATA_DIR, "olist_geolocation_dataset.csv"),
    "customers": os.path.join(BASE_DATA_DIR, "olist_customers_dataset.csv"),
    "sellers": os.path.join(BASE_DATA_DIR, "olist_sellers_dataset.csv"),
    "products": os.path.join(BASE_DATA_DIR, "olist_products_dataset.csv"),
    "category_translation": os.path.join(BASE_DATA_DIR, "product_category_name_translation.csv"),
    "orders": os.path.join(BASE_DATA_DIR, "olist_orders_dataset.csv"),
    "order_items": os.path.join(BASE_DATA_DIR, "olist_order_items_dataset.csv"),
    "payments": os.path.join(BASE_DATA_DIR, "olist_payments_dataset.csv"),
    "reviews": os.path.join(BASE_DATA_DIR, "olist_reviews_dataset.csv"),
}

# Ensure reports directory exists
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Logging Configuration
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(REPORTS_DIR, "etl_pipeline.log"), mode='w')
        ]
    )
    return logging.getLogger("ETL_Pipeline")

logger = setup_logging()
