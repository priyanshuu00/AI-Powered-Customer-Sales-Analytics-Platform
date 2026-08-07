import streamlit as st

def apply_theme():
    # Inject custom CSS for dark theme and modern KPI cards
    st.markdown("""
        <style>
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        .kpi-card {
            background-color: #1E2127;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            margin: 10px 0;
        }
        .kpi-title {
            font-size: 14px;
            color: #8C8C8C;
            text-transform: uppercase;
        }
        .kpi-value {
            font-size: 28px;
            font-weight: bold;
            color: #4CAF50;
        }
        </style>
    """, unsafe_allow_html=True)
