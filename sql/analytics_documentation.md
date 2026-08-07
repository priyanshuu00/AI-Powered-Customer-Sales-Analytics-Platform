# Phase 4: SQL Analytics Engine Documentation

This documentation provides a comprehensive overview of the SQL Analytics Engine constructed for the AI-Powered Customer Intelligence & Sales Analytics Platform. The engine acts as the robust data-retrieval backbone for all subsequent business intelligence reporting and dashboarding efforts.

## Directory Structure & Purpose
All SQL scripts reside in the `sql/` directory and are logically grouped:
- **`indexes.sql`**: High-impact performance tuning. Sets up index creation statements to drastically improve query performance for frequent joins and time-series analyses.
- **`basic_queries.sql`**: Fundamental queries. Calculates high-level aggregates and simple filtering to surface top-level business KPIs and summary statistics.
- **`advanced_queries.sql`**: Complex analytics. Employs advanced SQL features (CTEs, Window Functions) for deep-dive customer, product, and sales trend analysis.
- **`views.sql`**: Virtual tables. Encapsulates complex, multi-table queries into clean, reusable views (e.g., `vw_sales_summary`), ensuring that any BI tool connecting to the database has simplified access to core metrics.
- **`stored_procedures.sql`**: Parameterized routines. Provides dynamic, on-demand query capabilities, such as fetching a specific customer's order history or analyzing sales between two custom dates.

---

## 1. Key Performance Indicators (KPIs)
The `basic_queries.sql` file defines the core metrics of the business:

- **Total Revenue**: The sum of all successful payment values. *Business Meaning: Overall financial volume.*
- **Total Orders**: The count of all unique orders placed. *Business Meaning: Transactional volume.*
- **Total Customers**: The distinct count of `customer_unique_id`s. *Business Meaning: Overall user base size.*
- **Active Customers**: Distinct count of unique customers with at least one 'delivered' order. *Business Meaning: Effectively converted customer base.*
- **Repeat Customers**: Count of unique customers who have made more than one order. *Business Meaning: Brand loyalty proxy.*
- **Average Order Value (AOV)**: Total Revenue divided by Total Orders. *Business Meaning: Indicates purchasing power; higher AOV generally equates to better profit margins.*
- **Average Delivery Time**: The average number of days between the purchase timestamp and the customer delivery date. *Business Meaning: Key logistical health indicator.*
- **Cancellation Rate**: The percentage of total orders marked as 'canceled'. *Business Meaning: Measures friction in the fulfillment pipeline or customer dissatisfaction.*

---

## 2. Customer Analytics
Calculated via a blend of standard `GROUP BY` and advanced SQL constructs:

- **Customer Distribution**: Aggregates users by state and city to identify geographical hot spots.
- **Customer Segmentation**: A foundational RFM (Recency, Frequency, Monetary) approach using CTEs and `CASE` statements to categorize users into 'VIP', 'Loyal', 'Regular', or 'One-Time' buckets based on their lifetime spend and purchase frequency.
- **Customer Lifetime Value (CLV)**: Estimates the average revenue a customer generates over their entire relationship with the platform.
- **Repeat Purchase Rate**: The explicit percentage of the user base that returns for subsequent purchases.

---

## 3. Product & Sales Analytics
Leveraging robust `JOIN` operations (including `LEFT JOIN` on translations to prevent dropping unmapped Portuguese categories):

- **Product Performance**: Ranks individual products by both sheer volume (units sold) and financial value (revenue).
- **Category Analytics**: Rolls up product performance into categories to identify macro-level winners (e.g., 'Top Categories') and losers ('Least Performing Categories').
- **Sales Trends (Time-Series)**: Uses `DATE_FORMAT` and `YEARWEEK` to calculate Daily, Weekly, Monthly, Quarterly, and Yearly sales.
- **Revenue Growth**: Utilizes the `LAG()` Window Function to compare current month revenue to the previous month, outputting a precise Month-over-Month growth percentage.
- **Geographical Sales**: Uses the `RANK()` Window Function to order Brazilian states strictly by the revenue they generate.

---

## 4. Payment & Review Analytics
- **Payment Distribution**: Analyzes preferred payment types (credit card, boleto, etc.) and average transaction sizes for each.
- **Installment Analysis**: Groups payments by the number of installments chosen, providing insight into consumer credit reliance.
- **Customer Satisfaction**: Averages review scores across different product categories and specific sellers, filtering out low-volume entities (`HAVING total_reviews > 30`) to ensure statistical relevance.

---

## 5. Query Optimization Strategy
The `indexes.sql` file implements a targeted indexing strategy essential for handling large-scale e-commerce data:

- **Foreign Key Indexing**: Columns like `customer_id`, `order_id`, `product_id`, and `seller_id` are explicitly indexed to speed up the heavy `JOIN` operations required across this highly normalized (3NF) schema.
- **Time-Series Optimization**: `order_purchase_timestamp` is indexed to drastically accelerate `WHERE` clause date filtering, monthly aggregations, and window functions.
- **Categorical Optimization**: `payment_type` is indexed to speed up distribution counts.
- **User Optimization**: `customer_unique_id` is indexed to optimize retention metrics (e.g., counting repeat purchases).

---

## 6. Expected Outputs
By deploying this SQL Analytics Engine, analysts can:
1. Immediately connect a BI tool (like Tableau or PowerBI) to the structured `views`.
2. Run rapid ad-hoc analyses using the optimized index structure.
3. Automatically generate month-over-month growth reports using the advanced CTEs provided.

This Phase cleanly fulfills the requirement of building a robust, SQL-native analytics layer without bleeding into dashboarding or Python-based machine learning.
