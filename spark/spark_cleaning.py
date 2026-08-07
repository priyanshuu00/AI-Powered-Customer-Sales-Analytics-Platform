from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from pyspark.sql.types import TimestampType, DoubleType
from typing import Dict
from .spark_config import setup_logger

logger = setup_logger("SparkCleaning")

class SparkCleaner:
    @staticmethod
    def clean_datasets(dfs: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        logger.info("Starting data cleaning process...")
        cleaned = {}
        
        # 1. Orders
        if "orders" in dfs:
            orders_df = dfs["orders"].dropDuplicates()
            time_cols = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"]
            for col in time_cols:
                orders_df = orders_df.withColumn(col, F.to_timestamp(F.col(col)))
            cleaned["orders"] = orders_df
            
        # 2. Order Items
        if "order_items" in dfs:
            items_df = dfs["order_items"].dropDuplicates()
            items_df = items_df.withColumn("shipping_limit_date", F.to_timestamp(F.col("shipping_limit_date")))
            items_df = items_df.withColumn("price", F.col("price").cast(DoubleType()))
            cleaned["order_items"] = items_df
            
        # 3. Reviews
        if "reviews" in dfs:
            reviews_df = dfs["reviews"].dropDuplicates()
            reviews_df = reviews_df.fillna({"review_comment_title": "", "review_comment_message": ""})
            cleaned["reviews"] = reviews_df
            
        # 4. Products
        if "products" in dfs:
            prod_df = dfs["products"].dropDuplicates()
            prod_df = prod_df.fillna({"product_weight_g": 0, "product_length_cm": 0, "product_height_cm": 0, "product_width_cm": 0})
            cleaned["products"] = prod_df
            
        # Others (Simple deduplication)
        for name in ["customers", "payments", "sellers", "geolocation", "translation"]:
            if name in dfs:
                cleaned[name] = dfs[name].dropDuplicates()
                
        logger.info("Data cleaning completed.")
        return cleaned
