import streamlit as st
import pandas as pd
from charts import ChartBuilder

def render_review_dashboard(df: pd.DataFrame):
    st.header("Review Dashboard")
    
    if df.empty:
        st.warning("No review data available.")
        return
        
    df['rating_bucket'] = pd.cut(df['average_score'], bins=[0, 2.5, 3.5, 5.0], labels=['Negative', 'Neutral', 'Positive'])
    dist = df['rating_bucket'].value_counts().reset_index()
    dist.columns = ['Sentiment', 'Count']
    
    fig = ChartBuilder.pie_chart(dist, 'Sentiment', 'Count', 'Review Sentiment Distribution')
    st.plotly_chart(fig, use_container_width=True)
