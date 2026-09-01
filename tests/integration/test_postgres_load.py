"""Opt-in live PostgreSQL warehouse and Python/SQL reconciliation tests."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from sales_analytics.analysis.kpis import calculate_kpis
from sales_analytics.config import Settings
from sales_analytics.pipeline.extract import read_raw_sales
from sales_analytics.pipeline.load import load_warehouse
from sales_analytics.pipeline.transform import transform_sales

pytestmark = pytest.mark.integration
requires_postgres = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 to run destructive local warehouse tests",
)


@pytest.fixture(scope="module")
def live_warehouse():
    settings = Settings.from_env()
    raw = read_raw_sales(Path("data/raw/sales.csv"))
    warehouse = transform_sales(raw)
    load_warehouse(warehouse, settings, rebuild=True)
    return settings, raw, warehouse, calculate_kpis(warehouse)


def assert_close(actual, expected, tolerance=1e-8) -> None:
    assert float(actual) == pytest.approx(float(expected), rel=tolerance, abs=0.01)


@requires_postgres
def test_physical_counts_and_integrity(live_warehouse) -> None:
    settings, raw, warehouse, _ = live_warehouse
    expected_counts = {
        "dim_date": 1_096,
        "dim_customer": 3_777,
        "dim_category": 4,
        "dim_product": 24,
        "dim_channel": 3,
        "fact_sales": 50_000,
    }
    with psycopg.connect(settings.psycopg_dsn) as connection:
        for table, expected in expected_counts.items():
            actual = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert actual == expected
        failures = connection.execute(
            """
            SELECT COUNT(*) FROM fact_sales
            WHERE revenue <> ROUND(unit_price * quantity * (1 - discount), 2)
               OR total_cost <> ROUND(unit_cost * quantity, 2)
               OR profit <> revenue - total_cost
            """
        ).fetchone()[0]
    assert len(raw) == len(warehouse.fact_sales) == 50_000
    assert failures == 0


@requires_postgres
def test_sql_reconciles_with_python_kpis(live_warehouse) -> None:
    settings, _, _, python = live_warehouse
    with psycopg.connect(settings.psycopg_dsn, row_factory=dict_row) as connection:
        overview = connection.execute(
            """
            WITH customer_orders AS (
                SELECT customer_key, COUNT(DISTINCT transaction_id) AS orders
                FROM fact_sales GROUP BY customer_key
            )
            SELECT SUM(revenue) AS total_revenue, SUM(profit) AS total_profit,
                SUM(profit) / NULLIF(SUM(revenue), 0) AS gross_margin,
                COUNT(DISTINCT transaction_id) AS transactions,
                SUM(quantity) AS units_sold,
                SUM(revenue) / COUNT(DISTINCT transaction_id) AS aov,
                COUNT(DISTINCT customer_key) AS unique_customers,
                (SELECT COUNT(*) FROM customer_orders WHERE orders >= 2)
                    AS repeat_customers
            FROM fact_sales
            """
        ).fetchone()
        annual = connection.execute(
            """
            SELECT dates.year, SUM(facts.revenue) AS revenue,
                SUM(facts.profit) AS profit
            FROM fact_sales AS facts JOIN dim_date AS dates USING (date_key)
            GROUP BY dates.year ORDER BY dates.year
            """
        ).fetchall()
        products = connection.execute(
            """
            SELECT products.product_id, SUM(facts.revenue) AS revenue,
                SUM(facts.profit) AS profit
            FROM fact_sales AS facts JOIN dim_product AS products USING (product_key)
            GROUP BY products.product_id ORDER BY revenue DESC
            """
        ).fetchall()
        regions = connection.execute(
            """
            SELECT customers.region, SUM(facts.revenue) AS revenue,
                SUM(facts.profit) AS profit
            FROM fact_sales AS facts JOIN dim_customer AS customers USING (customer_key)
            GROUP BY customers.region ORDER BY customers.region
            """
        ).fetchall()
        channels = connection.execute(
            """
            SELECT channels.channel_name, SUM(facts.revenue) AS revenue,
                SUM(facts.profit) AS profit,
                SUM(facts.profit) / SUM(facts.revenue) AS gross_margin,
                SUM(facts.revenue) / COUNT(DISTINCT facts.transaction_id) AS aov
            FROM fact_sales AS facts JOIN dim_channel AS channels USING (channel_key)
            GROUP BY channels.channel_name ORDER BY channels.channel_name
            """
        ).fetchall()
        concentration = connection.execute(
            """
            WITH customers AS (
                SELECT customer_key, SUM(revenue) AS revenue
                FROM fact_sales GROUP BY customer_key
            ), ranked AS (
                SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rank,
                    SUM(revenue) OVER () AS total_revenue FROM customers
            )
            SELECT SUM(revenue) FILTER (WHERE rank <= 10) / MAX(total_revenue) AS share
            FROM ranked
            """
        ).fetchone()["share"]

    for key in ["total_revenue", "total_profit", "gross_margin"]:
        assert_close(overview[key], python.overview[key])
    assert overview["transactions"] == python.overview["transactions"]
    assert overview["units_sold"] == python.overview["units_sold"]
    assert overview["unique_customers"] == python.overview["unique_customers"]
    assert overview["repeat_customers"] == python.overview["repeat_customers"]
    assert_close(overview["aov"], python.overview["average_order_value"])
    assert_close(
        overview["repeat_customers"] / overview["unique_customers"],
        python.overview["repeat_customer_rate"],
    )

    for sql_row, python_row in zip(annual, python.annual.itertuples(), strict=True):
        assert sql_row["year"] == python_row.year
        assert_close(sql_row["revenue"], python_row.revenue)
        assert_close(sql_row["profit"], python_row.profit)
    for sql_row, python_row in zip(products, python.products.itertuples(), strict=True):
        assert sql_row["product_id"] == python_row.product_id
        assert_close(sql_row["revenue"], python_row.revenue)
        assert_close(sql_row["profit"], python_row.profit)

    for sql_row in regions:
        python_row = python.regions.set_index("region").loc[sql_row["region"]]
        assert_close(sql_row["revenue"], python_row["revenue"])
        assert_close(sql_row["profit"], python_row["profit"])
    for sql_row in channels:
        python_row = python.channels.set_index("channel_name").loc[
            sql_row["channel_name"]
        ]
        for sql_key, python_key in [
            ("revenue", "revenue"),
            ("profit", "profit"),
            ("gross_margin", "gross_margin"),
            ("aov", "average_order_value"),
        ]:
            assert_close(sql_row[sql_key], python_row[python_key])
    assert_close(concentration, python.concentration["top_customer_revenue_share"])
