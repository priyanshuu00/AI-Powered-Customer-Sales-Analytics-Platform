from pyspark.sql import DataFrame
import pyspark.sql.functions as F
from typing import Dict
from .spark_config import setup_logger

logger = setup_logger("SparkOptimizer")

class SparkOptimizer:
    @staticmethod
    def optimize(dfs: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
        logger.info("Applying optimizations (Cache, Persist, Broadcast Join, Repartition)...")
        
        if "orders" in dfs:
            # 1. Repartition and Cache: Orders are queried heavily by date.
            dfs["orders"] = dfs["orders"].repartition(F.year("order_purchase_timestamp"), F.month("order_purchase_timestamp"))
            dfs["orders"].cache() 
            
        if "order_items" in dfs:
            # 2. Coalesce: Reduce partitions if they are too small
            dfs["order_items"] = dfs["order_items"].coalesce(5)
            dfs["order_items"].cache()
            
        if "translation" in dfs:
            # 3. Broadcast Join Prep: Translation is a very small lookup table.
            dfs["translation"] = F.broadcast(dfs["translation"])
            
        if "payments" in dfs:
            # 4. Persist: Save payments for multiple aggregations
            dfs["payments"].persist() 
            
        return dfs
