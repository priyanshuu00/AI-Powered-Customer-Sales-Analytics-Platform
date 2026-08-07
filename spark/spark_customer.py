from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from .spark_config import setup_logger

logger = setup_logger("SparkCustomerAnalytics")

class SparkCustomerAnalyzer:
    @staticmethod
    def analyze(customers: DataFrame, orders: DataFrame, payments: DataFrame) -> DataFrame:
        logger.info("Running Customer Analytics...")
        
        df = customers.join(orders, on="customer_id").join(payments, on="order_id")
        
        # Repeat Customers and LTV
        customer_metrics = df.groupBy("customer_unique_id") \
                             .agg(F.sum("payment_value").alias("lifetime_value"),
                                  F.countDistinct("order_id").alias("total_orders")) \
                             .orderBy(F.desc("lifetime_value"))
                             
        return customer_metrics
