-- Run with: make db-check
-- Each violation_count must equal zero.

SELECT 'orphan_date_keys' AS check_name, COUNT(*) AS violation_count
FROM fact_sales AS facts
LEFT JOIN dim_date AS dates USING (date_key)
WHERE dates.date_key IS NULL
UNION ALL
SELECT 'orphan_customer_keys', COUNT(*)
FROM fact_sales AS facts
LEFT JOIN dim_customer AS customers USING (customer_key)
WHERE customers.customer_key IS NULL
UNION ALL
SELECT 'orphan_product_keys', COUNT(*)
FROM fact_sales AS facts
LEFT JOIN dim_product AS products USING (product_key)
WHERE products.product_key IS NULL
UNION ALL
SELECT 'orphan_channel_keys', COUNT(*)
FROM fact_sales AS facts
LEFT JOIN dim_channel AS channels USING (channel_key)
WHERE channels.channel_key IS NULL
UNION ALL
SELECT 'orphan_category_keys', COUNT(*)
FROM dim_product AS products
LEFT JOIN dim_category AS categories USING (category_key)
WHERE categories.category_key IS NULL
UNION ALL
SELECT 'duplicate_customer_ids', COUNT(*)
FROM (
    SELECT customer_id FROM dim_customer GROUP BY customer_id HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'duplicate_product_ids', COUNT(*)
FROM (
    SELECT product_id FROM dim_product GROUP BY product_id HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'duplicate_category_names', COUNT(*)
FROM (
    SELECT category_name
    FROM dim_category
    GROUP BY category_name
    HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'duplicate_channel_names', COUNT(*)
FROM (
    SELECT channel_name
    FROM dim_channel
    GROUP BY channel_name
    HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'duplicate_sales_lines', COUNT(*)
FROM (
    SELECT transaction_id, line_number
    FROM fact_sales
    GROUP BY transaction_id, line_number
    HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'financial_reconciliation_failures', COUNT(*)
FROM fact_sales
WHERE revenue <> ROUND(unit_price * quantity * (1 - discount), 2)
   OR total_cost <> ROUND(unit_cost * quantity, 2)
   OR profit <> revenue - total_cost
UNION ALL
SELECT 'unexpected_fact_nulls', COUNT(*)
FROM fact_sales
WHERE transaction_id IS NULL OR line_number IS NULL OR date_key IS NULL
   OR customer_key IS NULL OR product_key IS NULL OR channel_key IS NULL
   OR quantity IS NULL OR unit_price IS NULL OR discount IS NULL
   OR revenue IS NULL OR unit_cost IS NULL OR total_cost IS NULL OR profit IS NULL
UNION ALL
SELECT 'unexpected_dimension_nulls',
    (SELECT COUNT(*) FROM dim_date
        WHERE full_date IS NULL OR month IS NULL OR year IS NULL)
    + (SELECT COUNT(*) FROM dim_customer
        WHERE customer_id IS NULL OR region IS NULL)
    + (SELECT COUNT(*) FROM dim_category WHERE category_name IS NULL)
    + (SELECT COUNT(*) FROM dim_product
        WHERE product_id IS NULL OR product_name IS NULL OR category_key IS NULL)
    + (SELECT COUNT(*) FROM dim_channel WHERE channel_name IS NULL);

-- Record this value and reconcile it to the raw CSV row count.
SELECT COUNT(*) AS fact_row_count FROM fact_sales;
