-- indexes.sql
USE sales_analytics_db;

-- Part 9: Query Optimization

-- Indexes for frequent JOINs and filtering
CREATE INDEX idx_customer_id ON customers(customer_id);
CREATE INDEX idx_order_id_items ON order_items(order_id);
CREATE INDEX idx_order_id_payments ON payments(order_id);
CREATE INDEX idx_order_id_reviews ON reviews(order_id);
CREATE INDEX idx_product_id ON order_items(product_id);
CREATE INDEX idx_seller_id ON order_items(seller_id);

-- Indexes for Time-Series Analysis and trend queries
CREATE INDEX idx_order_purchase_timestamp ON orders(order_purchase_timestamp);

-- Index for Payment distribution analytics
CREATE INDEX idx_payment_type ON payments(payment_type);

-- Index for customer grouping and retention
CREATE INDEX idx_customer_unique_id ON customers(customer_unique_id);
