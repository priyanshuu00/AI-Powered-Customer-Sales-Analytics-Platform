-- stored_procedures.sql
USE olist_analytics;

-- Drop procedures if they exist to avoid conflicts on re-runs
DROP PROCEDURE IF EXISTS GetCustomerOrderHistory;
DROP PROCEDURE IF EXISTS GetCategorySalesByDateRange;

DELIMITER //

-- Procedure 1: Get Customer Order History
-- Given a customer_unique_id, returns their complete order history.
CREATE PROCEDURE GetCustomerOrderHistory(IN p_customer_unique_id VARCHAR(32))
BEGIN
    SELECT 
        o.order_id,
        o.order_purchase_timestamp,
        o.order_status,
        SUM(p.payment_value) AS order_total
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN payments p ON o.order_id = p.order_id
    WHERE c.customer_unique_id = p_customer_unique_id
    GROUP BY 
        o.order_id,
        o.order_purchase_timestamp,
        o.order_status
    ORDER BY o.order_purchase_timestamp DESC;
END //

-- Procedure 2: Get Category Sales By Date Range
-- Allows dynamic querying of category performance over a specific timeframe.
CREATE PROCEDURE GetCategorySalesByDateRange(
    IN p_start_date DATE,
    IN p_end_date DATE
)
BEGIN
    SELECT 
        IFNULL(ct.product_category_name_english, 'Unknown') AS category,
        SUM(oi.price) AS total_revenue,
        COUNT(oi.order_item_id) AS units_sold
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
    WHERE DATE(o.order_purchase_timestamp) BETWEEN p_start_date AND p_end_date
    GROUP BY category
    ORDER BY total_revenue DESC;
END //

DELIMITER ;
