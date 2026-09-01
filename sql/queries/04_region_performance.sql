WITH region_year AS (
    SELECT customers.region, dates.year, SUM(facts.revenue) AS revenue,
        SUM(facts.profit) AS profit,
        SUM(facts.profit) / NULLIF(SUM(facts.revenue), 0) AS gross_margin
    FROM fact_sales AS facts
    JOIN dim_customer AS customers USING (customer_key)
    JOIN dim_date AS dates USING (date_key)
    GROUP BY customers.region, dates.year
), comparison AS (
    SELECT *, LAG(revenue) OVER (PARTITION BY region ORDER BY year) AS prior_revenue,
        LAG(profit) OVER (PARTITION BY region ORDER BY year) AS prior_profit
    FROM region_year
)
SELECT region, year, revenue, profit, gross_margin,
    (revenue - prior_revenue) / NULLIF(prior_revenue, 0) AS revenue_yoy_growth,
    (profit - prior_profit) / NULLIF(prior_profit, 0) AS profit_yoy_growth
FROM comparison
ORDER BY year, revenue_yoy_growth DESC NULLS LAST;
