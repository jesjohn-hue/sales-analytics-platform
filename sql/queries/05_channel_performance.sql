SELECT channels.channel_name, SUM(facts.revenue) AS revenue,
    SUM(facts.profit) AS profit,
    SUM(facts.profit) / NULLIF(SUM(facts.revenue), 0) AS gross_margin,
    COUNT(DISTINCT facts.transaction_id) AS transactions,
    SUM(facts.revenue) / NULLIF(COUNT(DISTINCT facts.transaction_id), 0) AS average_order_value,
    SUM(facts.quantity) AS units_sold,
    COUNT(DISTINCT facts.customer_key) AS unique_customers
FROM fact_sales AS facts
JOIN dim_channel AS channels USING (channel_key)
GROUP BY channels.channel_name
ORDER BY revenue DESC;
