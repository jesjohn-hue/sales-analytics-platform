# Canonical KPI Definitions

All KPIs use completed synthetic sales in `fact_sales`, one row per transaction
product line. Currency is USD. Unless filtered, the period is the full dataset.
Ratios return null when their denominator is zero.

| KPI | Business definition and formula | Grain / time behavior | Caveat |
|---|---|---|---|
| Total Revenue | Earned sales after discounts. Numerator: `SUM(revenue)`; no denominator. | Additive across lines and periods. | Excludes tax, shipping, returns, and cancellations. |
| Total Profit | Gross profit after product cost. Numerator: `SUM(profit)` = revenue − total cost. | Additive across lines and periods. | Not operating or net profit. |
| Gross Margin % | Profit retained per revenue dollar. Numerator: `SUM(profit)`; denominator: `SUM(revenue)`. | Recalculate from totals at every grain; never average row margins. | Null when revenue is zero. |
| Number of Transactions | Distinct completed orders: `COUNT(DISTINCT transaction_id)`. | Distinct within the selected period/dimension. | Never count sales lines as orders. |
| Units Sold | `SUM(quantity)`. | Additive across lines and periods. | Units are not normalized for product value. |
| Average Order Value | Revenue per order. Numerator: total revenue; denominator: distinct transactions. | Recalculate within each filter context. | Multi-line orders must be deduplicated. |
| Average Revenue per Customer | Revenue divided by distinct purchasing customers. | Recalculate within the selected period. | Not contractual or recurring ARPU. |
| Unique Customers | `COUNT(DISTINCT customer_key)` with at least one sale. | Distinct within the selected period. | Excludes customers with no purchase. |
| Repeat Customer Rate | Customers with at least two distinct transactions divided by customers with at least one transaction. | Repeat behavior is measured within the selected analysis period. | Not a cohort retention rate. |
| YoY Revenue Growth | `(current-year revenue − prior-year revenue) / prior-year revenue`. | Annual; first year and zero prior year are null. | Compare complete like-for-like years. |
| YoY Profit Growth | `(current-year profit − prior-year profit) / prior-year profit`. | Annual; first year and zero prior year are null. | Negative prior profit needs separate interpretation. |
| Region Performance | Revenue, profit, and aggregate margin grouped by customer region. | Current filter context; annual cuts support growth. | Region is the customer’s stable dataset region. |
| Product Performance | Revenue, profit, margin, units, and ranks grouped by product. | Current filter context. | Revenue rank must be read with profit/margin guardrails. |
| Category Performance | Revenue, profit, margin, and growth grouped by product category. | Current context; latest YoY compares category years. | Mix changes can drive aggregate margin. |
| Channel Performance | Revenue, profit, margin, transactions, and AOV grouped by channel. | Current filter context. | Channel AOV reflects both units and order-line mix. |
| Monthly Trends | Revenue and profit grouped by calendar month. | Calendar months in chronological order. | Monthly seasonality is intentionally present. |
| Top/Bottom Products | Dense ranks by revenue or profit; bottom uses ascending profit. | Rank within the selected period. | Small products may rank poorly because of scale. |
| Customer Lifetime Revenue | `SUM(revenue)` per customer over the available dataset. | Cumulative only within the dataset window. | Not true lifetime value and excludes acquisition/service costs. |
| Top Customer Concentration | Revenue from the 10 highest-revenue customers divided by total revenue. | Recalculate for the selected period. | A fixed top 10 is project-specific, not an industry benchmark. |

The SQL files in `sql/queries` are the warehouse implementation. Python
`calculate_kpis()` independently applies the same definitions to transformed
frames for validation.
