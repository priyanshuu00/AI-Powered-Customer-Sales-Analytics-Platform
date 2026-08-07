# Interview Guide

*Note: Due to length constraints, a representative sample of questions covering the core concepts of this project is provided below.*

## SQL Questions (Sample)
1. **Q:** How did you optimize the `total_revenue` query in MySQL?
   **A:** By creating indexes on `order_id` and `customer_id`, and using materialized Views to pre-aggregate daily sales, preventing the dashboard from calculating sums on raw tables.
2. **Q:** Explain 3NF and why you used it here.
   **A:** Third Normal Form eliminates transitive dependencies. We used it to ensure data integrity across customers, orders, and payments before running analytics.

## Python Questions
1. **Q:** Why use SQLAlchemy instead of raw `mysql-connector` cursors for bulk inserts?
   **A:** SQLAlchemy allows Pandas `to_sql` integration, which manages chunking and transaction batching natively, drastically improving ETL load times.
2. **Q:** How did you handle missing data in Pandas?
   **A:** By dropping rows missing critical foreign keys, and imputing domain-specific defaults (e.g., setting unknown product weights to 0).

## ETL Questions
1. **Q:** What happens if the ETL fails midway?
   **A:** The ETL is designed to be idempotent. It truncates tables prior to insertion (or uses `if_exists='replace'`), ensuring we don't duplicate data on a retry.

## Apache Spark Questions
1. **Q:** Explain how you used `Broadcast` joins in Phase 6.
   **A:** The `category_translation` table was extremely small. Broadcasting it to all worker nodes prevented a costly shuffle operation when joining it with the massive `order_items` table.
2. **Q:** Why use `repartition` vs `coalesce`?
   **A:** I used `repartition` on `orders` by `year/month` to evenly distribute data for time-series analysis, which causes a full shuffle. I used `coalesce` when saving final outputs to reduce the number of output partitions without a full shuffle.

## Streamlit Questions
1. **Q:** How did you prevent the dashboard from crashing the database?
   **A:** By heavily utilizing `@st.cache_data`. The app queries the database once per session, caches the resulting DataFrame, and subsequent UI filters run instantly in Pandas memory.

## AI / Gemini Questions
1. **Q:** How did you prevent the LLM from making up false sales numbers?
   **A:** We did not give the LLM database access. Instead, we executed exact SQL queries, converted the results to JSON, and injected that JSON into a strict prompt, restricting the LLM to only interpreting the provided facts.

## Business Analytics Questions
1. **Q:** What defines a High Value Customer in your pipeline?
   **A:** A customer whose Lifetime Value (sum of `payment_value`) falls in the top percentile, calculated via RFM (Recency, Frequency, Monetary) grouping in the analytical engine.
