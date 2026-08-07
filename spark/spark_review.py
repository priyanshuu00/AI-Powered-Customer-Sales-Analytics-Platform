from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from .spark_config import setup_logger

logger = setup_logger("SparkReviewAnalytics")

class SparkReviewAnalyzer:
    @staticmethod
    def analyze(reviews: DataFrame) -> DataFrame:
        logger.info("Running Review Analytics...")
        
        review_dist = reviews.groupBy("review_score") \
                             .count() \
                             .withColumnRenamed("count", "total_reviews") \
                             .orderBy(F.desc("review_score"))
                             
        return review_dist
