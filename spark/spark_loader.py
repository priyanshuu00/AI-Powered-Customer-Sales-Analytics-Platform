import os
from pyspark.sql import SparkSession, DataFrame
from typing import Dict
from .spark_config import setup_logger

logger = setup_logger("SparkLoader")
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

class SparkLoader:
    def __init__(self, spark: SparkSession):
        self.spark = spark
        self.file_map = {
            "customers": "olist_customers_dataset.csv",
            "geolocation": "olist_geolocation_dataset.csv",
            "order_items": "olist_order_items_dataset.csv",
            "payments": "olist_payments_dataset.csv",
            "reviews": "olist_reviews_dataset.csv",
            "orders": "olist_orders_dataset.csv",
            "products": "olist_products_dataset.csv",
            "sellers": "olist_sellers_dataset.csv",
            "translation": "product_category_name_translation.csv"
        }

    def load_datasets(self) -> Dict[str, DataFrame]:
        logger.info("Loading datasets into Spark...")
        dfs = {}
        for name, filename in self.file_map.items():
            path = os.path.join(BASE_DATA_DIR, filename)
            if os.path.exists(path):
                df = self.spark.read.csv(path, header=True, inferSchema=True)
                dfs[name] = df
                logger.info(f"Loaded {name}: {df.count()} records, {df.rdd.getNumPartitions()} partitions.")
            else:
                logger.warning(f"File not found: {path}")
        return dfs
