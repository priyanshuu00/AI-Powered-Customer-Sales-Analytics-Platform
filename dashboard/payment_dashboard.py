import streamlit as st
import pandas as pd
from charts import ChartBuilder

def render_payment_dashboard(df: pd.DataFrame):
    st.header("Payment Dashboard")
    
    if df.empty:
        st.warning("No payment data available.")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        fig = ChartBuilder.pie_chart(df, 'payment_type', 'transaction_count', 'Payment Type Distribution (Count)')
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        fig2 = ChartBuilder.bar_chart(df, 'payment_type', 'total_volume', 'Payment Volume by Type')
        st.plotly_chart(fig2, use_container_width=True)
