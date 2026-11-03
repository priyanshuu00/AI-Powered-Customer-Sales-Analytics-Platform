-- views.sql
-- Keep this aligned with DB_NAME in .env (default: sales_analytics_db).
USE sales_analytics_db;

-- Part 7: Business Views

-- 1. vw_sales_summary
CREATE OR REPLACE VIEW vw_sales_summary AS
SELECT 
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp,
    c.customer_state,
    SUM(p.payment_value) AS total_order_value
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY 
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp,
    c.customer_state;

-- 2. vw_customer_summary
CREATE OR REPLACE VIEW vw_customer_summary AS
SELECT 
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS lifetime_orders,
    SUM(p.payment_value) AS lifetime_spent
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id
LEFT JOIN payments p ON o.order_id = p.order_id
GROUP BY 
    c.customer_unique_id,
    c.customer_city,
    c.customer_state;

-- 3. vw_product_performance
CREATE OR REPLACE VIEW vw_product_performance AS
SELECT 
    p.product_id,
    IFNULL(ct.product_category_name_english, 'Unknown') AS category_name,
    COUNT(oi.order_item_id) AS units_sold,
    SUM(oi.price) AS total_revenue
FROM products p
LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
LEFT JOIN order_items oi ON p.product_id = oi.product_id
GROUP BY 
    p.product_id,
    category_name;

-- 4. vw_monthly_sales
CREATE OR REPLACE VIEW vw_monthly_sales AS
SELECT 
    DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS sale_month,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(total_order_value) AS total_revenue
FROM vw_sales_summary
GROUP BY sale_month;

-- 5. vw_payment_summary
CREATE OR REPLACE VIEW vw_payment_summary AS
SELECT 
    payment_type,
    COUNT(order_id) AS transaction_count,
    SUM(payment_value) AS total_volume,
    AVG(payment_value) AS average_transaction_value
FROM payments
GROUP BY payment_type;

-- 6. vw_review_summary
CREATE OR REPLACE VIEW vw_review_summary AS
SELECT 
    order_id,
    AVG(review_score) AS average_score,
    COUNT(review_id) AS review_count
FROM reviews
GROUP BY order_id;

-- 7. vw_top_customers
CREATE OR REPLACE VIEW vw_top_customers AS
SELECT 
    customer_unique_id,
    lifetime_spent,
    lifetime_orders
FROM vw_customer_summary
ORDER BY lifetime_spent DESC;

-- 8. vw_category_performance
CREATE OR REPLACE VIEW vw_category_performance AS
SELECT 
    category_name,
    SUM(units_sold) AS total_units_sold,
    SUM(total_revenue) AS total_category_revenue
FROM vw_product_performance
GROUP BY category_name;
