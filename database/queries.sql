-- Phase 2 Database Queries Placeholder
-- These queries are intended for data exploration and future analytics.

USE olist_analytics;

-- 1. Sales Performance (Revenue by Month)
-- Useful for identifying seasonal trends in sales.
/*
SELECT 
    DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS sale_month,
    SUM(oi.price + oi.freight_value) AS total_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY sale_month
ORDER BY sale_month;
*/

-- 2. Customer Cohort Analysis
-- Identifies returning customers vs one-time buyers.
/*
SELECT 
    c.customer_unique_id, 
    COUNT(o.order_id) AS total_orders
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_unique_id
ORDER BY total_orders DESC;
*/

-- 3. Product Category Performance
-- Which product categories generate the most revenue?
/*
SELECT 
    ct.product_category_name_english, 
    COUNT(oi.order_item_id) AS units_sold,
    SUM(oi.price) AS total_sales
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY ct.product_category_name_english
ORDER BY total_sales DESC
LIMIT 10;
*/

-- 4. Seller Performance and Logistics
-- Average freight value and delivery time by seller.
/*
SELECT 
    s.seller_id,
    COUNT(oi.order_id) as total_orders_fulfilled,
    AVG(oi.freight_value) as avg_freight_value
FROM sellers s
JOIN order_items oi ON s.seller_id = oi.seller_id
GROUP BY s.seller_id
ORDER BY total_orders_fulfilled DESC
LIMIT 10;
*/

-- 5. Customer Satisfaction
-- Average review score per product category.
/*
SELECT 
    ct.product_category_name_english, 
    AVG(r.review_score) AS average_score,
    COUNT(r.review_id) AS total_reviews
FROM reviews r
JOIN order_items oi ON r.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY ct.product_category_name_english
HAVING total_reviews > 50
ORDER BY average_score DESC;
*/
