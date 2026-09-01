WITH customer_value AS (
    SELECT customers.customer_id, customers.region,
        SUM(facts.revenue) AS lifetime_revenue,
        SUM(facts.profit) AS lifetime_profit,
        COUNT(DISTINCT facts.transaction_id) AS transactions
    FROM fact_sales AS facts
    JOIN dim_customer AS customers USING (customer_key)
    GROUP BY customers.customer_id, customers.region
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (ORDER BY lifetime_revenue DESC) AS revenue_rank,
        SUM(lifetime_revenue) OVER () AS total_revenue
    FROM customer_value
)
SELECT customer_id, region, lifetime_revenue, lifetime_profit, transactions,
    revenue_rank, lifetime_revenue / NULLIF(total_revenue, 0) AS revenue_share
FROM ranked
ORDER BY revenue_rank;

WITH customer_value AS (
    SELECT customer_key, SUM(revenue) AS revenue
    FROM fact_sales GROUP BY customer_key
), ranked AS (
    SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rank,
        SUM(revenue) OVER () AS total_revenue
    FROM customer_value
)
SELECT SUM(revenue) FILTER (WHERE rank <= 10) AS top_10_revenue,
    SUM(revenue) FILTER (WHERE rank <= 10) / NULLIF(MAX(total_revenue), 0) AS top_10_revenue_share
FROM ranked;
