import pandas as pd
from typing import Dict, Any
from sqlalchemy import create_engine
from .config import DB_URI, logger

def load_data(dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Loads transformed DataFrames into MySQL in dependency order."""
    logger.info("Loading Started")
    
    try:
        engine = create_engine(DB_URI)
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise

    # Define the loading order to respect foreign key constraints
    load_order = [
        "geolocation",
        "category_translation",
        "customers",
        "sellers",
        "products",
        "orders",
        "order_items",
        "payments",
        "reviews"
    ]
    
    load_stats = {}

    with engine.begin() as connection:
        for table_name in load_order:
            if table_name in dfs and not dfs[table_name].empty:
                logger.info(f"Loading table {table_name}...")
                df = dfs[table_name]
                try:
                    # using if_exists='append' because schema is already created
                    df.to_sql(name=table_name, con=connection, if_exists='append', index=False, chunksize=10000)
                    load_stats[table_name] = len(df)
                    logger.info(f"Loaded {len(df)} rows into {table_name}.")
                except Exception as e:
                    logger.error(f"Failed to load table {table_name}. Transaction will be rolled back. Error: {e}")
                    raise
            else:
                logger.warning(f"Table {table_name} has no data to load or was not extracted.")
                load_stats[table_name] = 0

    logger.info("Loading Completed Successfully")
    return load_stats
