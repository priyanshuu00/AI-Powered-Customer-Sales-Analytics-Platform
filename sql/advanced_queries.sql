-- advanced_queries.sql
USE olist_analytics;

-- ==========================================
-- Part 2: Customer Analytics (Advanced)
-- ==========================================

-- Top Customers (By Revenue)
SELECT 
    c.customer_unique_id, 
    SUM(p.payment_value) AS total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY c.customer_unique_id
ORDER BY total_spent DESC
LIMIT 10;

-- Customer Segmentation (RFM-like Analysis basics)
WITH CustomerSpend AS (
    SELECT 
        c.customer_unique_id, 
        COUNT(DISTINCT o.order_id) AS frequency,
        SUM(p.payment_value) AS monetary
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT 
    customer_unique_id,
    frequency,
    monetary,
    CASE 
        WHEN frequency >= 3 AND monetary > 500 THEN 'VIP'
        WHEN frequency >= 2 AND monetary > 200 THEN 'Loyal'
        WHEN frequency = 1 THEN 'One-Time'
        ELSE 'Regular'
    END AS customer_segment
FROM CustomerSpend;

-- Customer Lifetime Value (CLV)
-- Simplified CLV: Average Order Value * Purchase Frequency
WITH CustomerMetrics AS (
    SELECT 
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(p.payment_value) AS total_revenue
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT 
    AVG(total_revenue / total_orders) * AVG(total_orders) AS avg_customer_lifetime_value
FROM CustomerMetrics;

-- Repeat Purchase Rate
WITH OrderCounts AS (
    SELECT customer_unique_id, COUNT(order_id) as order_count
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    GROUP BY customer_unique_id
)
SELECT 
    (SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*)) * 100 AS repeat_purchase_rate
FROM OrderCounts;


-- ==========================================
-- Part 3: Product Analytics (Advanced)
-- ==========================================

-- Revenue by Product
SELECT 
    oi.product_id, 
    SUM(oi.price) AS product_revenue
FROM order_items oi
GROUP BY oi.product_id
ORDER BY product_revenue DESC
LIMIT 10;

-- Revenue by Category
SELECT 
    IFNULL(ct.product_category_name_english, 'Unknown') AS category,
    SUM(oi.price) AS category_revenue
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY category
ORDER BY category_revenue DESC;

-- Top Categories
SELECT 
    IFNULL(ct.product_category_name_english, 'Unknown') AS category,
    COUNT(oi.order_item_id) AS units_sold
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY category
ORDER BY units_sold DESC
LIMIT 10;

-- Least Performing Categories
SELECT 
    IFNULL(ct.product_category_name_english, 'Unknown') AS category,
    COUNT(oi.order_item_id) AS units_sold
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY category
ORDER BY units_sold ASC
LIMIT 10;


-- ==========================================
-- Part 4: Sales Analytics (Advanced / Trends)
-- ==========================================

-- Daily Sales
SELECT 
    DATE(order_purchase_timestamp) AS sale_date,
    SUM(payment_value) AS daily_revenue
FROM orders o
JOIN payments p ON o.order_id = p.order_id
GROUP BY sale_date
ORDER BY sale_date;

-- Weekly Sales
SELECT 
    YEARWEEK(order_purchase_timestamp) AS sale_week,
    SUM(payment_value) AS weekly_revenue
FROM orders o
JOIN payments p ON o.order_id = p.order_id
GROUP BY sale_week
ORDER BY sale_week;

-- Monthly Sales & Revenue Growth (Using LAG Window Function)
WITH MonthlySales AS (
    SELECT 
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS sale_month,
        SUM(payment_value) AS monthly_revenue
    FROM orders o
    JOIN payments p ON o.order_id = p.order_id
    GROUP BY sale_month
)
SELECT 
    sale_month,
    monthly_revenue,
    LAG(monthly_revenue) OVER(ORDER BY sale_month) AS prev_month_revenue,
    ((monthly_revenue - LAG(monthly_revenue) OVER(ORDER BY sale_month)) / LAG(monthly_revenue) OVER(ORDER BY sale_month)) * 100 AS growth_percentage
FROM MonthlySales;

-- Quarterly Sales
SELECT 
    CONCAT(YEAR(order_purchase_timestamp), '-Q', QUARTER(order_purchase_timestamp)) AS sale_quarter,
    SUM(payment_value) AS quarterly_revenue
FROM orders o
JOIN payments p ON o.order_id = p.order_id
GROUP BY sale_quarter
ORDER BY sale_quarter;

-- Yearly Sales
SELECT 
    YEAR(order_purchase_timestamp) AS sale_year,
    SUM(payment_value) AS yearly_revenue
FROM orders o
JOIN payments p ON o.order_id = p.order_id
GROUP BY sale_year
ORDER BY sale_year;

-- Order Trends (Count of orders over time)
SELECT 
    DATE_FORMAT(order_purchase_timestamp, '%Y-%m') AS order_month,
    COUNT(order_id) as total_orders
FROM orders
GROUP BY order_month
ORDER BY order_month;

-- Sales by State (Using RANK)
SELECT 
    c.customer_state,
    SUM(p.payment_value) AS state_revenue,
    RANK() OVER(ORDER BY SUM(p.payment_value) DESC) as revenue_rank
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY c.customer_state;

-- Sales by City (Top 10)
SELECT 
    c.customer_city,
    SUM(p.payment_value) AS city_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN payments p ON o.order_id = p.order_id
GROUP BY c.customer_city
ORDER BY city_revenue DESC
LIMIT 10;


-- ==========================================
-- Part 5: Payment Analytics (Advanced)
-- ==========================================

-- Installment Analysis
SELECT 
    payment_installments,
    COUNT(*) AS frequency,
    AVG(payment_value) AS avg_value_per_installment_tier
FROM payments
GROUP BY payment_installments
ORDER BY payment_installments;


-- ==========================================
-- Part 6: Review Analytics (Advanced)
-- ==========================================

-- Rating by Product Category
SELECT 
    IFNULL(ct.product_category_name_english, 'Unknown') AS category,
    AVG(r.review_score) AS avg_rating,
    COUNT(r.review_id) AS total_reviews
FROM reviews r
JOIN order_items oi ON r.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
GROUP BY category
HAVING total_reviews > 50
ORDER BY avg_rating DESC;

-- Rating by Seller
SELECT 
    s.seller_id,
    AVG(r.review_score) AS avg_seller_rating,
    COUNT(r.review_id) AS total_reviews
FROM reviews r
JOIN order_items oi ON r.order_id = oi.order_id
JOIN sellers s ON oi.seller_id = s.seller_id
GROUP BY s.seller_id
HAVING total_reviews > 30
ORDER BY avg_seller_rating DESC
LIMIT 20;
