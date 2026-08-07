import logging
from pyspark.sql import SparkSession

def setup_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(name)

def get_spark_session(app_name: str = "Olist_Analytics") -> SparkSession:
    logger = setup_logger("SparkConfig")
    logger.info("Initializing SparkSession...")
    spark = SparkSession.builder \
        .appName(app_name) \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.executor.memory", "4g") \
        .config("spark.sql.shuffle.partitions", "10") \
        .config("spark.default.parallelism", "10") \
        .getOrCreate()
    logger.info("SparkSession initialized successfully.")
    return spark
