import pandas as pd
from typing import Dict, Any
from .config import logger

def check_missing_values(df: pd.DataFrame, df_name: str) -> Dict[str, int]:
    missing = df.isnull().sum()
    missing_dict = missing[missing > 0].to_dict()
    if missing_dict:
        logger.warning(f"[{df_name}] Missing values found: {missing_dict}")
    return missing_dict

def check_duplicate_rows(df: pd.DataFrame, df_name: str) -> int:
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        logger.warning(f"[{df_name}] Duplicate rows found: {duplicates}")
    return int(duplicates)

def check_null_primary_keys(df: pd.DataFrame, df_name: str, pk_col: str) -> int:
    if pk_col in df.columns:
        null_pks = df[pk_col].isnull().sum()
        if null_pks > 0:
            logger.warning(f"[{df_name}] Null Primary Keys found in {pk_col}: {null_pks}")
        return int(null_pks)
    return 0

def check_empty_strings(df: pd.DataFrame, df_name: str) -> Dict[str, int]:
    empty_strings = {}
    for col in df.select_dtypes(include=['object']):
        empty_count = (df[col] == "").sum()
        if empty_count > 0:
            empty_strings[col] = int(empty_count)
            logger.warning(f"[{df_name}] Empty strings found in {col}: {empty_count}")
    return empty_strings

def validate_data(dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Validates extracted DataFrames and returns statistics."""
    logger.info("Validation Started")
    validation_stats = {}
    
    # Primary Keys definition for checks
    pks = {
        "geolocation": "geolocation_zip_code_prefix",
        "category_translation": "product_category_name",
        "customers": "customer_id",
        "sellers": "seller_id",
        "products": "product_id",
        "orders": "order_id"
    }

    for name, df in dfs.items():
        logger.info(f"Validating {name}...")
        stats = {
            "total_rows": len(df),
            "missing_values": check_missing_values(df, name),
            "duplicate_rows": check_duplicate_rows(df, name),
            "empty_strings": check_empty_strings(df, name),
            "null_pks": check_null_primary_keys(df, name, pks.get(name)) if pks.get(name) else 0
        }
        validation_stats[name] = stats
        
    logger.info("Validation Completed")
    return validation_stats
