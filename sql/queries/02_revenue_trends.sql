-- Monthly trend shows seasonality; annual comparisons use equal complete years.
SELECT DATE_TRUNC('month', dates.full_date)::DATE AS month,
    SUM(facts.revenue) AS revenue, SUM(facts.profit) AS profit,
    SUM(facts.profit) / NULLIF(SUM(facts.revenue), 0) AS gross_margin,
    COUNT(DISTINCT facts.transaction_id) AS transactions
FROM fact_sales AS facts
JOIN dim_date AS dates USING (date_key)
GROUP BY DATE_TRUNC('month', dates.full_date)
ORDER BY month;

WITH category_year AS (
    SELECT categories.category_name, dates.year,
        SUM(facts.revenue) AS revenue, SUM(facts.profit) AS profit
    FROM fact_sales AS facts
    JOIN dim_date AS dates USING (date_key)
    JOIN dim_product AS products USING (product_key)
    JOIN dim_category AS categories USING (category_key)
    GROUP BY categories.category_name, dates.year
), comparison AS (
    SELECT *, LAG(revenue) OVER (PARTITION BY category_name ORDER BY year) AS prior_revenue
    FROM category_year
)
SELECT category_name, year, revenue, profit,
    (revenue - prior_revenue) / NULLIF(prior_revenue, 0) AS revenue_yoy_growth
FROM comparison
ORDER BY category_name, year;
