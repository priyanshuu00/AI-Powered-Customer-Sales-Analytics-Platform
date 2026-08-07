from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from .spark_config import setup_logger

logger = setup_logger("SparkSalesAnalytics")

class SparkSalesAnalyzer:
    @staticmethod
    def analyze(orders: DataFrame, payments: DataFrame) -> DataFrame:
        logger.info("Running Sales Analytics...")
        
        sales = orders.join(payments, on="order_id", how="inner")
        
        # Monthly Revenue
        monthly_sales = sales.withColumn("month", F.date_format("order_purchase_timestamp", "yyyy-MM")) \
                             .groupBy("month") \
                             .agg(F.sum("payment_value").alias("monthly_revenue"),
                                  F.count("order_id").alias("total_orders")) \
                             .orderBy("month")
                             
        return monthly_sales
