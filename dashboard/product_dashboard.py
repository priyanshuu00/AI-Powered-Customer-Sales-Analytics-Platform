import streamlit as st
import pandas as pd
from charts import ChartBuilder

def render_product_dashboard(df: pd.DataFrame):
    st.header("Product Dashboard")
    
    if df.empty:
        st.warning("No product data available.")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        top_cats = df.sort_values('total_category_revenue', ascending=False).head(10)
        fig = ChartBuilder.bar_chart(top_cats, 'category_name', 'total_category_revenue', 'Top 10 Categories by Revenue')
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        fig2 = ChartBuilder.pie_chart(top_cats, 'category_name', 'total_units_sold', 'Top 10 Categories by Units Sold')
        st.plotly_chart(fig2, use_container_width=True)
