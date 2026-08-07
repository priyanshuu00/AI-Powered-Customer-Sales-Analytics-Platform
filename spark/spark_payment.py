from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from .spark_config import setup_logger

logger = setup_logger("SparkPaymentAnalytics")

class SparkPaymentAnalyzer:
    @staticmethod
    def analyze(payments: DataFrame) -> DataFrame:
        logger.info("Running Payment Analytics...")
        
        payment_dist = payments.groupBy("payment_type") \
                               .agg(F.count("order_id").alias("transaction_count"),
                                    F.avg("payment_value").alias("avg_payment")) \
                               .orderBy(F.desc("transaction_count"))
                               
        return payment_dist
