-- Rebuild the dimensional warehouse in dependency-safe order.
-- This file is intentionally repeatable for local development.

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_category;
DROP TABLE IF EXISTS dim_channel;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day SMALLINT NOT NULL CHECK (day BETWEEN 1 AND 31),
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name VARCHAR(9) NOT NULL,
    quarter SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    year SMALLINT NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    day_of_week VARCHAR(9) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    CONSTRAINT ck_dim_date_key_matches_date CHECK (
        date_key = EXTRACT(YEAR FROM full_date)::INTEGER * 10000
            + EXTRACT(MONTH FROM full_date)::INTEGER * 100
            + EXTRACT(DAY FROM full_date)::INTEGER
    )
);

CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY CHECK (customer_key > 0),
    customer_id VARCHAR(20) NOT NULL UNIQUE,
    region VARCHAR(50) NOT NULL,
    CONSTRAINT ck_dim_customer_id_format
        CHECK (customer_id ~ '^CUST[0-9]{5}$')
);

CREATE TABLE dim_category (
    category_key INTEGER PRIMARY KEY CHECK (category_key > 0),
    category_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY CHECK (product_key > 0),
    product_id VARCHAR(20) NOT NULL UNIQUE,
    product_name VARCHAR(150) NOT NULL,
    category_key INTEGER NOT NULL REFERENCES dim_category (category_key),
    CONSTRAINT ck_dim_product_id_format
        CHECK (product_id ~ '^PROD[0-9]{3}$')
);

CREATE TABLE dim_channel (
    channel_key INTEGER PRIMARY KEY CHECK (channel_key > 0),
    channel_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE fact_sales (
    sales_key BIGINT PRIMARY KEY CHECK (sales_key > 0),
    transaction_id VARCHAR(20) NOT NULL,
    line_number SMALLINT NOT NULL CHECK (line_number > 0),
    date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    customer_key INTEGER NOT NULL REFERENCES dim_customer (customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product (product_key),
    channel_key INTEGER NOT NULL REFERENCES dim_channel (channel_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price > 0),
    discount NUMERIC(5, 4) NOT NULL CHECK (discount BETWEEN 0 AND 1),
    revenue NUMERIC(14, 2) NOT NULL CHECK (revenue >= 0),
    unit_cost NUMERIC(12, 2) NOT NULL CHECK (unit_cost >= 0),
    total_cost NUMERIC(14, 2) NOT NULL CHECK (total_cost >= 0),
    profit NUMERIC(14, 2) NOT NULL,
    CONSTRAINT uq_fact_sales_transaction_line UNIQUE (transaction_id, line_number),
    CONSTRAINT ck_fact_sales_transaction_id_format
        CHECK (transaction_id ~ '^TXN[0-9]{7}$'),
    CONSTRAINT ck_fact_sales_revenue_calculation CHECK (
        revenue = ROUND(unit_price * quantity * (1 - discount), 2)
    ),
    CONSTRAINT ck_fact_sales_cost_calculation CHECK (
        total_cost = ROUND(unit_cost * quantity, 2)
    ),
    CONSTRAINT ck_fact_sales_profit_calculation CHECK (
        profit = revenue - total_cost
    )
);

-- Foreign-key indexes support the primary BI slicing and joining paths.
CREATE INDEX idx_fact_sales_date_key ON fact_sales (date_key);
CREATE INDEX idx_fact_sales_customer_key ON fact_sales (customer_key);
CREATE INDEX idx_fact_sales_product_key ON fact_sales (product_key);
CREATE INDEX idx_fact_sales_channel_key ON fact_sales (channel_key);
