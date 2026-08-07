from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from .spark_config import setup_logger

logger = setup_logger("SparkProductAnalytics")

class SparkProductAnalyzer:
    @staticmethod
    def analyze(items: DataFrame, products: DataFrame, translation: DataFrame) -> DataFrame:
        logger.info("Running Product Analytics...")
        
        # Broadcast Join on translation
        df = items.join(products, on="product_id") \
                  .join(translation, on="product_category_name", how="left")
                  
        cat_metrics = df.groupBy("product_category_name_english") \
                        .agg(F.sum("price").alias("category_revenue"),
                             F.count("order_item_id").alias("units_sold")) \
                        .orderBy(F.desc("category_revenue"))
                        
        return cat_metrics
