WITH product_performance AS (
    SELECT products.product_id, products.product_name, categories.category_name,
        SUM(facts.revenue) AS revenue, SUM(facts.profit) AS profit,
        SUM(facts.profit) / NULLIF(SUM(facts.revenue), 0) AS gross_margin,
        SUM(facts.quantity) AS units_sold
    FROM fact_sales AS facts
    JOIN dim_product AS products USING (product_key)
    JOIN dim_category AS categories USING (category_key)
    GROUP BY products.product_id, products.product_name, categories.category_name
)
SELECT *, RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
    RANK() OVER (ORDER BY profit DESC) AS profit_rank,
    RANK() OVER (ORDER BY profit ASC) AS bottom_profit_rank
FROM product_performance
ORDER BY revenue_rank;

-- High-revenue products below the portfolio's aggregate margin warrant review.
WITH portfolio AS (
    SELECT SUM(profit) / NULLIF(SUM(revenue), 0) AS margin FROM fact_sales
), products AS (
    SELECT product_key, SUM(revenue) AS revenue, SUM(profit) AS profit,
        SUM(profit) / NULLIF(SUM(revenue), 0) AS margin
    FROM fact_sales GROUP BY product_key
)
SELECT dimensions.product_id, dimensions.product_name, products.revenue,
    products.profit, products.margin
FROM products
JOIN dim_product AS dimensions USING (product_key)
CROSS JOIN portfolio
WHERE products.revenue >= (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue) FROM products)
  AND products.margin < portfolio.margin
ORDER BY products.margin, products.revenue DESC;
