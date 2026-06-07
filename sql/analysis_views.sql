-- ============================================================
-- Customer Spend Analytics  -  Analysis Views
-- ============================================================
-- These views feed the Power BI dashboard pages and the HTML
-- dashboard. Each view is small and self-contained so Power BI
-- can import via Direct Query or a quick CSV refresh.
-- ============================================================

DROP VIEW IF EXISTS vw_monthly_revenue;
DROP VIEW IF EXISTS vw_customer_segments;
DROP VIEW IF EXISTS vw_top_products;
DROP VIEW IF EXISTS vw_country_spend;
DROP VIEW IF EXISTS vw_state_spend;
DROP VIEW IF EXISTS vw_category_spend;
DROP VIEW IF EXISTS vw_anomalous_customers;
DROP VIEW IF EXISTS vw_cancellation_by_state;
DROP VIEW IF EXISTS vw_kpis;
DROP VIEW IF EXISTS vw_top_customers;

-- 1. Monthly revenue trend ----------------------------------------
CREATE VIEW vw_monthly_revenue AS
SELECT
    year_month,
    year,
    month,
    ROUND(SUM(total_amount), 2) AS revenue,
    COUNT(DISTINCT order_id)    AS orders,
    COUNT(DISTINCT customer_id) AS customers,
    ROUND(SUM(total_amount) * 1.0 / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM transactions
GROUP BY year_month, year, month
ORDER BY year_month;

-- 2. Customer segments breakdown ----------------------------------
CREATE VIEW vw_customer_segments AS
SELECT
    c.segment,
    COUNT(*)                            AS customer_count,
    ROUND(SUM(c.monetary), 2)           AS total_spend,
    ROUND(AVG(c.monetary), 2)           AS avg_spend,
    ROUND(AVG(c.frequency), 2)          AS avg_frequency,
    ROUND(AVG(c.recency_days), 2)       AS avg_recency_days
FROM customers c
GROUP BY c.segment
ORDER BY total_spend DESC;

-- 3. Top 20 products by revenue -----------------------------------
CREATE VIEW vw_top_products AS
SELECT
    sku,
    style,
    category,
    units_sold,
    orders,
    ROUND(revenue, 2) AS revenue
FROM products
ORDER BY revenue DESC
LIMIT 20;

-- 4. Country-level spend ------------------------------------------
CREATE VIEW vw_country_spend AS
SELECT
    ship_country                    AS country,
    COUNT(DISTINCT order_id)        AS orders,
    COUNT(DISTINCT customer_id)     AS customers,
    ROUND(SUM(total_amount), 2)     AS revenue
FROM transactions
GROUP BY ship_country
ORDER BY revenue DESC;

-- 5. State-level spend (India) ------------------------------------
CREATE VIEW vw_state_spend AS
SELECT
    ship_state                      AS state,
    COUNT(DISTINCT order_id)        AS orders,
    COUNT(DISTINCT customer_id)     AS customers,
    ROUND(SUM(total_amount), 2)     AS revenue
FROM transactions
WHERE ship_state IS NOT NULL AND ship_state <> ''
GROUP BY ship_state
ORDER BY revenue DESC;

-- 6. Category-level spend -----------------------------------------
CREATE VIEW vw_category_spend AS
SELECT
    category,
    SUM(qty)                        AS units_sold,
    COUNT(DISTINCT order_id)        AS orders,
    ROUND(SUM(total_amount), 2)     AS revenue
FROM transactions
GROUP BY category
ORDER BY revenue DESC;

-- 7. Anomalous customers: spike > 200% vs personal average --------
CREATE VIEW vw_anomalous_customers AS
WITH per_customer_order AS (
    SELECT
        customer_id,
        order_id,
        SUM(total_amount) AS order_total
    FROM transactions
    GROUP BY customer_id, order_id
),
stats AS (
    SELECT
        customer_id,
        AVG(order_total) AS avg_order,
        MAX(order_total) AS max_order,
        COUNT(*)         AS n_orders
    FROM per_customer_order
    GROUP BY customer_id
)
SELECT
    s.customer_id,
    s.n_orders,
    ROUND(s.avg_order, 2) AS avg_order_value,
    ROUND(s.max_order, 2) AS peak_order_value,
    ROUND((s.max_order - s.avg_order) * 100.0 / s.avg_order, 1) AS spike_pct,
    c.segment,
    c.state,
    c.is_high_value
FROM stats s
LEFT JOIN customers c USING (customer_id)
WHERE s.n_orders >= 2
  AND s.avg_order > 0
  AND (s.max_order - s.avg_order) * 100.0 / s.avg_order >= 200
ORDER BY spike_pct DESC
LIMIT 100;

-- 8. Cancellations by state ---------------------------------------
CREATE VIEW vw_cancellation_by_state AS
SELECT
    ship_state                            AS state,
    COUNT(*)                              AS cancelled_orders,
    ROUND(SUM(amount), 2)                 AS cancelled_amount
FROM cancelled_orders
WHERE ship_state IS NOT NULL AND ship_state <> ''
GROUP BY ship_state
ORDER BY cancelled_orders DESC;

-- 9. Executive KPI snapshot ---------------------------------------
CREATE VIEW vw_kpis AS
SELECT
    (SELECT ROUND(SUM(total_amount), 2)       FROM transactions)             AS total_revenue,
    (SELECT COUNT(DISTINCT order_id)          FROM transactions)             AS total_orders,
    (SELECT COUNT(DISTINCT customer_id)       FROM transactions)             AS unique_customers,
    (SELECT ROUND(AVG(order_total), 2) FROM (
        SELECT SUM(total_amount) order_total
        FROM transactions GROUP BY order_id))                                AS avg_order_value,
    (SELECT COUNT(*) FROM cancelled_orders)                                  AS cancelled_orders,
    (SELECT ROUND(100.0 * (SELECT COUNT(*) FROM cancelled_orders) /
           ((SELECT COUNT(DISTINCT order_id) FROM transactions) +
            (SELECT COUNT(*) FROM cancelled_orders)), 2))                    AS cancellation_rate_pct;

-- 10. Top 20 high-value customers ---------------------------------
CREATE VIEW vw_top_customers AS
SELECT
    customer_id,
    state,
    city,
    segment,
    frequency,
    ROUND(monetary, 2) AS monetary,
    recency_days,
    rfm_score
FROM customers
ORDER BY monetary DESC
LIMIT 20;
