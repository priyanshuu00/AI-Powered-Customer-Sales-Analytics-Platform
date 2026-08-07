# Technical Report

## 1. Abstract
This report summarizes the technical engineering decisions made during the construction of the AI-Powered Customer Intelligence Platform, spanning data modeling, distributed processing, and AI integrations.

## 2. Data Modeling Strategy
The database was structured in 3rd Normal Form (3NF). While a Star Schema (Kimball methodology) is often preferred for Data Warehouses, 3NF was chosen here to closely mirror the raw transactional state of the provided dataset, ensuring that the ETL pipeline could focus heavily on referential integrity and data-cleaning constraints rather than complex dimension mapping.
To satisfy OLAP query requirements, heavy indexing was applied to foreign keys, and materialized-style Views were constructed to pre-aggregate data for the Dashboard.

## 3. Scalability with Apache Spark
While Pandas is sufficient for the ~100MB Olist dataset, Pandas operates entirely in memory and is bounded by a single thread. To future-proof the architecture, Apache Spark was integrated in Phase 6. By explicitly calling `repartition()` on chronological boundaries and `broadcast()` on small lookup tables, the pipeline is fully prepared to scale horizontally across an AWS EMR or Databricks cluster if the data volume enters the Terabyte scale.

## 4. AI Hallucination Mitigation
Generative LLMs are prone to hallucination. To prevent the Gemini API from inventing sales data, we do *not* allow the AI to run queries directly. Instead, the deterministic Python layer executes statistical functions, packages the results into JSON objects, and injects them into a highly constrained prompt. The AI is specifically instructed to *only* base its Root Cause Analysis on the injected JSON.

## 5. Dashboard Performance (Streamlit)
To prevent the Streamlit application from crushing the database under load every time a user toggles a UI filter, `@st.cache_data` is heavily utilized. The application hits the database exactly once per session, loads the summarized views into RAM, and all subsequent filtering is handled optimally by Pandas.
