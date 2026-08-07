import pandas as pd
from typing import Dict
from .config import logger

def drop_duplicates_all(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    for name, df in dfs.items():
        original_len = len(df)
        dfs[name] = df.drop_duplicates()
        if len(dfs[name]) < original_len:
            logger.info(f"[{name}] Dropped {original_len - len(dfs[name])} duplicate rows.")
    return dfs

def handle_missing_values(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    if "reviews" in dfs:
        dfs["reviews"]["review_comment_title"] = dfs["reviews"]["review_comment_title"].fillna("")
        dfs["reviews"]["review_comment_message"] = dfs["reviews"]["review_comment_message"].fillna("")
        
    if "products" in dfs:
        numeric_cols = [
            "product_name_lenght", "product_description_lenght", 
            "product_photos_qty", "product_weight_g", 
            "product_length_cm", "product_height_cm", "product_width_cm"
        ]
        for col in numeric_cols:
            if col in dfs["products"].columns:
                dfs["products"][col] = dfs["products"][col].fillna(0).astype(int)

    return dfs

def parse_timestamps(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    if "orders" in dfs:
        time_cols = [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date"
        ]
        for col in time_cols:
            if col in dfs["orders"].columns:
                dfs["orders"][col] = pd.to_datetime(dfs["orders"][col], errors='coerce')
                
    if "reviews" in dfs:
        for col in ["review_creation_date", "review_answer_timestamp"]:
            if col in dfs["reviews"].columns:
                dfs["reviews"][col] = pd.to_datetime(dfs["reviews"][col], errors='coerce')
                
    if "order_items" in dfs:
        if "shipping_limit_date" in dfs["order_items"].columns:
             dfs["order_items"]["shipping_limit_date"] = pd.to_datetime(dfs["order_items"]["shipping_limit_date"], errors='coerce')

    return dfs

def enforce_referential_integrity(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Removes orphaned records based on foreign keys to ensure clean loading."""
    
    if "geolocation" in dfs:
        dfs["geolocation"] = dfs["geolocation"].drop_duplicates(subset=["geolocation_zip_code_prefix"])

    if "customers" in dfs and "geolocation" in dfs:
        valid_zips = set(dfs["geolocation"]["geolocation_zip_code_prefix"])
        dfs["customers"] = dfs["customers"][dfs["customers"]["customer_zip_code_prefix"].isin(valid_zips)]
        
    if "sellers" in dfs and "geolocation" in dfs:
        valid_zips = set(dfs["geolocation"]["geolocation_zip_code_prefix"])
        dfs["sellers"] = dfs["sellers"][dfs["sellers"]["seller_zip_code_prefix"].isin(valid_zips)]

    if "orders" in dfs and "customers" in dfs:
        valid_customers = set(dfs["customers"]["customer_id"])
        dfs["orders"] = dfs["orders"][dfs["orders"]["customer_id"].isin(valid_customers)]
        
    if "order_items" in dfs:
        if "orders" in dfs:
            valid_orders = set(dfs["orders"]["order_id"])
            dfs["order_items"] = dfs["order_items"][dfs["order_items"]["order_id"].isin(valid_orders)]
        if "products" in dfs:
            valid_products = set(dfs["products"]["product_id"])
            dfs["order_items"] = dfs["order_items"][dfs["order_items"]["product_id"].isin(valid_products)]
        if "sellers" in dfs:
            valid_sellers = set(dfs["sellers"]["seller_id"])
            dfs["order_items"] = dfs["order_items"][dfs["order_items"]["seller_id"].isin(valid_sellers)]
            
    if "payments" in dfs and "orders" in dfs:
        valid_orders = set(dfs["orders"]["order_id"])
        dfs["payments"] = dfs["payments"][dfs["payments"]["order_id"].isin(valid_orders)]
        
    if "reviews" in dfs and "orders" in dfs:
        valid_orders = set(dfs["orders"]["order_id"])
        dfs["reviews"] = dfs["reviews"][dfs["reviews"]["order_id"].isin(valid_orders)]
        
    return dfs

def transform_data(dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Applies all cleaning and transformation steps to the DataFrames."""
    logger.info("Transformation Started")
    
    dfs = drop_duplicates_all(dfs)
    dfs = handle_missing_values(dfs)
    dfs = parse_timestamps(dfs)
    dfs = enforce_referential_integrity(dfs)
    
    logger.info("Transformation Completed")
    return dfs
