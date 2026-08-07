# Project Walkthrough

## 1. End-to-End Project Flow
The AI-Powered Customer Intelligence & Sales Analytics Platform is a comprehensive data engineering and analytics pipeline. It begins with raw, unstructured e-commerce data (CSV format) and moves through a structured ETL pipeline into a normalized MySQL Data Warehouse. From there, the data is processed by two distinct engines: a traditional SQL analytics engine for exact aggregations and a distributed Apache Spark engine for massive-scale processing. The aggregated results are visualized via a real-time Streamlit dashboard, while a Gemini-powered AI engine provides natural language insights and root-cause analysis.

## 2. Architecture Explanation
The system follows a modular, decoupled architecture:
- **Storage Layer**: MySQL ensures ACID compliance and data integrity.
- **Compute Layer**: Apache Spark handles distributed processing, while Python/Pandas handles localized EDA.
- **Serving Layer**: Streamlit acts as the BI presentation layer.
- **Intelligence Layer**: Google Gemini LLM provides predictive and diagnostic insights.

## 3. Technology Choices
- **MySQL**: Chosen for its robust relational model, which perfectly suits the highly structured nature of transactional e-commerce data.
- **Apache Spark**: Chosen to future-proof the application. While Pandas works for gigabytes of data, Spark scales to terabytes.
- **Streamlit**: Enables rapid, Pythonic deployment of interactive front-ends without writing separate React/Node backends.
- **Gemini AI**: Provides state-of-the-art context windowing, allowing us to pass massive JSON aggregations for analysis without token limits.

## 4. Data Flow
1. **Ingestion**: Raw `.csv` files are loaded via Pandas.
2. **Transformation**: Missing values are imputed, dates are cast, and duplicates are dropped.
3. **Loading**: SQLAlchemy efficiently streams data into MySQL.
4. **Aggregation**: SQL Views and PySpark RDDs aggregate millions of rows into key metrics (e.g., Monthly Sales).
5. **Presentation**: Streamlit queries the SQL Views and renders Plotly charts.
6. **Insight**: The Gemini AI consumes the aggregations and outputs Markdown reports.

## 5. Major Challenges
- **Memory Management**: Loading the entire dataset into Pandas occasionally caused memory spikes. This was mitigated by chunking and eventually migrating heavy workloads to Apache Spark.
- **Data Integrity**: The raw dataset contained orphaned foreign keys. The ETL pipeline had to be hardened to drop orphaned records before attempting MySQL inserts to prevent constraint violations.
- **AI Hallucination**: Open-ended prompts led to the LLM inventing data. This was solved by heavily constraining the prompt to *only* analyze injected, pre-calculated JSON metrics.

## 6. Scalability Discussion
To scale this from a local deployment to an enterprise cloud environment:
- **Storage**: Migrate MySQL to Amazon RDS or Snowflake.
- **Compute**: Migrate the Spark pipeline to Databricks or AWS EMR.
- **Orchestration**: Wrap the Python modules in Docker containers and orchestrate the DAG using Apache Airflow.
