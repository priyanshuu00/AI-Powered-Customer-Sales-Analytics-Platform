import pandas as pd

def apply_global_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    # A generic filter applier based on the dictionary passed from the sidebar
    filtered_df = df.copy()
    
    if filters.get("state") and "customer_state" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["customer_state"].isin(filters["state"])]
        
    if filters.get("city") and "customer_city" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["customer_city"].isin(filters["city"])]
        
    if filters.get("category") and "category_name" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["category_name"].isin(filters["category"])]
        
    if filters.get("payment_type") and "payment_type" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["payment_type"].isin(filters["payment_type"])]
        
    return filtered_df
