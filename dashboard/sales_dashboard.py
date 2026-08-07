import streamlit as st
import pandas as pd
from charts import ChartBuilder

def render_sales_dashboard(df: pd.DataFrame):
    st.header("Sales Dashboard")
    
    if df.empty:
        st.warning("No sales data available.")
        return
        
    df['order_purchase_timestamp'] = pd.to_datetime(df['order_purchase_timestamp'])
    
    # Monthly Sales
    monthly = df.groupby(df['order_purchase_timestamp'].dt.to_period('M'))['total_order_value'].sum().reset_index()
    monthly['order_purchase_timestamp'] = monthly['order_purchase_timestamp'].astype(str)
    
    col1, col2 = st.columns(2)
    with col1:
        fig_line = ChartBuilder.line_chart(monthly, 'order_purchase_timestamp', 'total_order_value', 'Revenue Trend (Monthly)')
        st.plotly_chart(fig_line, use_container_width=True)
        
    with col2:
        # Top States
        states = df.groupby('customer_state')['total_order_value'].sum().reset_index().sort_values('total_order_value', ascending=False).head(10)
        fig_bar = ChartBuilder.bar_chart(states, 'customer_state', 'total_order_value', 'Top 10 States by Revenue')
        st.plotly_chart(fig_bar, use_container_width=True)
