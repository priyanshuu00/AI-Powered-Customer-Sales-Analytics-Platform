-- basic_queries.sql
USE sales_analytics_db;

-- ==========================================
-- Part 1: KPI Queries
-- ==========================================

-- Total Revenue
SELECT SUM(payment_value) AS total_revenue FROM payments;

-- Total Orders
SELECT COUNT(order_id) AS total_orders FROM orders;

-- Total Customers
SELECT COUNT(DISTINCT customer_unique_id) AS total_customers FROM customers;

-- Active Customers (Customers who have made at least one delivered order)
SELECT COUNT(DISTINCT c.customer_unique_id) AS active_customers
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered';

-- Repeat Customers
SELECT COUNT(*) AS repeat_customers FROM (
    SELECT customer_unique_id
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY customer_unique_id
    HAVING COUNT(o.order_id) > 1
) sub;

-- Average Order Value
SELECT SUM(payment_value) / COUNT(DISTINCT order_id) AS average_order_value
FROM payments;

-- Average Products per Order
SELECT COUNT(order_item_id) / COUNT(DISTINCT order_id) AS avg_products_per_order
FROM order_items;

-- Total Payments
SELECT COUNT(payment_sequential) AS total_payments FROM payments;

-- Average Delivery Time (Days)
SELECT AVG(DATEDIFF(order_delivered_customer_date, order_purchase_timestamp)) AS avg_delivery_time_days
FROM orders
WHERE order_status = 'delivered';

-- Cancellation Rate
SELECT 
    (SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) / COUNT(*)) * 100 AS cancellation_rate_percentage
FROM orders;


-- ==========================================
-- Part 2: Customer Analytics (Basic)
-- ==========================================

-- Customer Distribution by State
SELECT customer_state, COUNT(DISTINCT customer_unique_id) AS customer_count
FROM customers
GROUP BY customer_state
ORDER BY customer_count DESC;

-- Customer Distribution by City (Top 10)
SELECT customer_city, COUNT(DISTINCT customer_unique_id) AS customer_count
FROM customers
GROUP BY customer_city
ORDER BY customer_count DESC
LIMIT 10;

-- New vs Returning Customers (Rough estimate: 1 order = New, >1 = Returning)
SELECT 
    CASE WHEN order_count = 1 THEN 'New' ELSE 'Returning' END AS customer_type,
    COUNT(customer_unique_id) AS num_customers
FROM (
    SELECT c.customer_unique_id, COUNT(o.order_id) AS order_count
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY c.customer_unique_id
) sub
GROUP BY customer_type;


-- ==========================================
-- Part 3: Product Analytics (Basic)
-- ==========================================

-- Best Selling Products (By Volume)
SELECT product_id, COUNT(order_item_id) AS units_sold
FROM order_items
GROUP BY product_id
ORDER BY units_sold DESC
LIMIT 10;

-- Worst Selling Products (By Volume)
SELECT product_id, COUNT(order_item_id) AS units_sold
FROM order_items
GROUP BY product_id
ORDER BY units_sold ASC
LIMIT 10;

-- Average Product Price
SELECT AVG(price) AS avg_product_price FROM order_items;


-- ==========================================
-- Part 5: Payment Analytics (Basic)
-- ==========================================

-- Payment Type Distribution
SELECT payment_type, COUNT(*) AS count, SUM(payment_value) as total_value
FROM payments
GROUP BY payment_type
ORDER BY count DESC;

-- Average Payment Value
SELECT payment_type, AVG(payment_value) AS avg_payment_value
FROM payments
GROUP BY payment_type
ORDER BY avg_payment_value DESC;


-- ==========================================
-- Part 6: Review Analytics (Basic)
-- ==========================================

-- Average Rating
SELECT AVG(review_score) AS average_rating FROM reviews;

-- Rating Distribution
SELECT review_score, COUNT(*) AS number_of_reviews
FROM reviews
GROUP BY review_score
ORDER BY review_score DESC;

-- One-Star Reviews Count
SELECT COUNT(*) AS one_star_reviews FROM reviews WHERE review_score = 1;

-- Five-Star Reviews Count
SELECT COUNT(*) AS five_star_reviews FROM reviews WHERE review_score = 5;
