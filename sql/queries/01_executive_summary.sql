-- Overall operating summary. Transactions are distinct orders, not fact rows.
WITH customer_orders AS (
    SELECT customer_key, COUNT(DISTINCT transaction_id) AS order_count
    FROM fact_sales
    GROUP BY customer_key
)
SELECT
    SUM(revenue) AS total_revenue,
    SUM(profit) AS total_profit,
    SUM(profit) / NULLIF(SUM(revenue), 0) AS gross_margin,
    COUNT(DISTINCT transaction_id) AS transactions,
    SUM(quantity) AS units_sold,
    SUM(revenue) / NULLIF(COUNT(DISTINCT transaction_id), 0) AS average_order_value,
    SUM(revenue) / NULLIF(COUNT(DISTINCT customer_key), 0) AS average_revenue_per_customer,
    COUNT(DISTINCT customer_key) AS unique_customers,
    (SELECT COUNT(*) FROM customer_orders WHERE order_count >= 2)::NUMERIC
        / NULLIF((SELECT COUNT(*) FROM customer_orders), 0) AS repeat_customer_rate
FROM fact_sales;

WITH annual AS (
    SELECT dates.year, SUM(facts.revenue) AS revenue, SUM(facts.profit) AS profit
    FROM fact_sales AS facts
    JOIN dim_date AS dates USING (date_key)
    GROUP BY dates.year
), comparison AS (
    SELECT *, LAG(revenue) OVER (ORDER BY year) AS prior_revenue,
        LAG(profit) OVER (ORDER BY year) AS prior_profit
    FROM annual
)
SELECT year, revenue, profit, profit / NULLIF(revenue, 0) AS gross_margin,
    (revenue - prior_revenue) / NULLIF(prior_revenue, 0) AS revenue_yoy_growth,
    (profit - prior_profit) / NULLIF(prior_profit, 0) AS profit_yoy_growth
FROM comparison
ORDER BY year;
