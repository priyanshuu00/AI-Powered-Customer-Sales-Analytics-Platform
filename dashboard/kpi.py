import streamlit as st
import pandas as pd

def render_kpis(sales_df: pd.DataFrame, customers_df: pd.DataFrame, reviews_df: pd.DataFrame):
    st.subheader("Executive Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # KPIs
    total_rev = sales_df['total_order_value'].sum() if not sales_df.empty else 0
    total_orders = sales_df['order_id'].nunique() if not sales_df.empty else 0
    total_customers = customers_df['customer_unique_id'].nunique() if not customers_df.empty else 0
    avg_rating = reviews_df['average_score'].mean() if not reviews_df.empty else 0
    
    with col1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Revenue</div><div class="kpi-value">${total_rev:,.2f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Orders</div><div class="kpi-value">{total_orders:,}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Total Customers</div><div class="kpi-value">{total_customers:,}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="kpi-card"><div class="kpi-title">Average Rating</div><div class="kpi-value">{avg_rating:.2f}</div></div>', unsafe_allow_html=True)
