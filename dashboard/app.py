import streamlit as st
import pandas as pd
from database import load_data
from theme import apply_theme
from sidebar import render_sidebar
from kpi import render_kpis
from sales_dashboard import render_sales_dashboard
from customer_dashboard import render_customer_dashboard
from product_dashboard import render_product_dashboard
from payment_dashboard import render_payment_dashboard
from review_dashboard import render_review_dashboard
from utils import get_csv_download_link

st.set_page_config(page_title="AI-Powered Sales Analytics", layout="wide")

apply_theme()

st.title("Business Analytics Dashboard")

# Load Data from MySQL Views (created in Phase 4)
df_sales = load_data("SELECT * FROM vw_sales_summary;")
df_customers = load_data("SELECT * FROM vw_customer_summary;")
df_categories = load_data("SELECT * FROM vw_category_performance;")
df_payments = load_data("SELECT * FROM vw_payment_summary;")
df_reviews = load_data("SELECT * FROM vw_review_summary;")

# Render Sidebar
filters = render_sidebar(df_sales)

# Apply Date Filter if present to sales
if "date_range" in filters and len(filters["date_range"]) == 2:
    start_date, end_date = filters["date_range"]
    if not df_sales.empty:
        mask = (df_sales['order_purchase_timestamp'].dt.date >= start_date) & (df_sales['order_purchase_timestamp'].dt.date <= end_date)
        df_sales = df_sales.loc[mask]

# Apply State Filter
if "state" in filters and filters["state"]:
    if not df_sales.empty:
        df_sales = df_sales[df_sales['customer_state'].isin(filters["state"])]

# Executive Overview
render_kpis(df_sales, df_customers, df_reviews)

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Sales", "Customers", "Products", "Payments", "Reviews"])

with tab1:
    render_sales_dashboard(df_sales)
    if not df_sales.empty:
        st.markdown(get_csv_download_link(df_sales, "sales_data.csv", "Export Sales CSV"), unsafe_allow_html=True)
        
with tab2:
    render_customer_dashboard(df_customers)
    
with tab3:
    render_product_dashboard(df_categories)
    
with tab4:
    render_payment_dashboard(df_payments)
    
with tab5:
    render_review_dashboard(df_reviews)
