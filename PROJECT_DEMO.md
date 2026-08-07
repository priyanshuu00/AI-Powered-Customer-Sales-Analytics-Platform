# 10-Minute Project Demo Script

## 1. Problem (1 min)
"Hello. E-commerce platforms generate millions of data points daily. Without an automated pipeline, analysts spend weeks manually downloading CSVs and building Excel charts. This project solves that by automating the entire lifecycle from raw data to AI-driven insights."

## 2. Dataset & Architecture (2 mins)
"We utilized the Olist E-commerce dataset containing 100,000+ orders. Our architecture is decoupled: Data is ingested via a Python ETL, stored in a 3NF MySQL Data Warehouse, processed by either SQL or Apache Spark, visualized in Streamlit, and analyzed by Google Gemini AI."

## 3. ETL & SQL (2 mins)
"Our ETL pipeline enforces strict referential integrity. Once in MySQL, we built an Analytics Engine using advanced SQL concepts like CTEs and Window Functions to pre-calculate metrics like Customer Lifetime Value, storing them in optimized Views."

## 4. Spark (2 mins)
"To demonstrate Enterprise Scalability, I built a parallel PySpark pipeline. By utilizing Broadcast joins for lookup tables and Repartitioning data by chronological dates, this architecture can scale from gigabytes to terabytes across a cluster without memory exhaustion."

## 5. Dashboard (2 mins)
"For the Business User, I built a real-time Streamlit dashboard. It queries our SQL Views and heavily utilizes caching so that filtering by state, category, or date is instantaneous and doesn't overload the database."

## 6. AI & Business Value (1 min)
"Finally, we integrated the Gemini LLM. It acts as a virtual Data Scientist, reading our aggregated JSON metrics and automatically generating Executive Summaries, Root Cause Analyses, and actionable business recommendations. Ultimately, this platform reduces time-to-insight from weeks to seconds."
