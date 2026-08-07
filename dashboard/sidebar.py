import streamlit as st
import pandas as pd

def render_sidebar(df_sales_summary: pd.DataFrame) -> dict:
    st.sidebar.header("Global Filters")
    
    filters = {}
    
    if st.sidebar.button("Reset Filters"):
        st.experimental_rerun()
        
    if not df_sales_summary.empty and 'order_purchase_timestamp' in df_sales_summary.columns:
        df_sales_summary['order_purchase_timestamp'] = pd.to_datetime(df_sales_summary['order_purchase_timestamp'])
        min_date = df_sales_summary['order_purchase_timestamp'].min().date()
        max_date = df_sales_summary['order_purchase_timestamp'].max().date()
        date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
        filters["date_range"] = date_range
        
    if not df_sales_summary.empty and 'customer_state' in df_sales_summary.columns:
        states = st.sidebar.multiselect("State Filter", options=sorted(df_sales_summary['customer_state'].dropna().unique()))
        filters["state"] = states
        
    return filters
