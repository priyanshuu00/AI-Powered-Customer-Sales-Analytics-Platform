# Project Architecture Defense

## Why did you choose MySQL?
**Answer:** The Olist dataset is a highly structured, relational e-commerce dataset (Orders, Customers, Payments, Items). MySQL enforces strict ACID compliance and referential integrity through Foreign Keys, preventing orphaned records. While a NoSQL database (like MongoDB) offers schema flexibility, it would make complex multi-table JOINs (essential for sales analytics) extremely inefficient.

## Why not PostgreSQL?
**Answer:** PostgreSQL is an excellent alternative and arguably superior for complex analytical Window Functions. However, MySQL is historically ubiquitous in legacy enterprise systems. Choosing MySQL demonstrates the ability to optimize queries (using indexes and CTEs) within a slightly more constrained, highly common environment.

## Why Spark?
**Answer:** While Pandas successfully processed the ~100MB dataset on a single machine, Pandas cannot scale beyond the physical RAM of a single node. Apache Spark was introduced to prove enterprise scalability. By using PySpark's resilient distributed datasets (RDDs/DataFrames), the pipeline is now capable of processing terabytes of data across a distributed cluster (e.g., AWS EMR) without code changes.

## Why Streamlit?
**Answer:** Streamlit allows Data Engineers and Scientists to rapidly prototype and deploy interactive front-ends purely in Python. Building a custom React/Node.js application would have added massive development overhead without adding analytical value. Streamlit securely wraps our SQL/Pandas logic into a production-grade BI interface in hours rather than weeks.

## Why Gemini?
**Answer:** Google's Gemini API offers an exceptionally large context window and strong reasoning capabilities. This allowed us to pass massive, aggregated JSON outputs directly into the prompt without hitting token limits, yielding highly accurate Root Cause Analyses and Strategic Recommendations compared to smaller models.

## How would you scale this?
**Answer:** 
1. **Orchestration:** Wrap the Python scripts in Airflow DAGs for automated, dependency-aware scheduling.
2. **Storage:** Migrate the local MySQL instance to a cloud data warehouse like Snowflake or AWS Redshift.
3. **Compute:** Deploy the PySpark modules to a managed Databricks cluster.

## What are the limitations?
**Answer:** 
1. **Batch Processing:** The current ETL is batch-oriented. It does not support real-time streaming (which would require Kafka/Flink).
2. **Local Infrastructure:** Currently designed to run locally via `.env` configurations.

## Future improvements?
**Answer:**
1. Implement a CI/CD pipeline using GitHub Actions to automate the `pytest` suite.
2. Containerize the application using Docker and `docker-compose` to ensure environment parity across deployments.
