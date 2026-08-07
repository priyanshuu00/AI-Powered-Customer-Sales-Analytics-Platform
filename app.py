"""
AI-Powered Customer Sales Analytics Platform
Main Streamlit Web Application Entry Point
"""

import streamlit as st

def main() -> None:
    """Initialize and run the Streamlit application layout."""
    st.set_page_config(
        page_title="AI-Powered Customer Sales Analytics Platform",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 AI-Powered Customer Sales Analytics Platform")
    st.markdown(
        "Welcome to the **AI-Powered Customer Sales Analytics Platform**. "
        "Navigate through the sidebar to explore Sales Trends, Customer RFM Segmentation, "
        "PySpark Big Data Analytics, and AI Executive Insights."
    )

if __name__ == "__main__":
    main()
