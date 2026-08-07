import streamlit as st
import pandas as pd
from charts import ChartBuilder

def render_customer_dashboard(df: pd.DataFrame):
    st.header("Customer Dashboard")
    
    if df.empty:
        st.warning("No customer data available.")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        # Customer Distribution (Top 10 cities)
        cities = df.groupby('customer_city')['customer_unique_id'].nunique().reset_index().sort_values('customer_unique_id', ascending=False).head(10)
        fig = ChartBuilder.bar_chart(cities, 'customer_unique_id', 'customer_city', 'Top 10 Cities by Customer Count', orientation='h')
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        # High Value Customers
        top_cust = df.sort_values('lifetime_spent', ascending=False).head(10)
        top_cust['customer_unique_id_short'] = top_cust['customer_unique_id'].str[:8]
        fig2 = ChartBuilder.bar_chart(top_cust, 'customer_unique_id_short', 'lifetime_spent', 'Top 10 Customers by Lifetime Value')
        st.plotly_chart(fig2, use_container_width=True)
