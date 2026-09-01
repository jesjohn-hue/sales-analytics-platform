"""Validation tests for canonical KPI calculations and analytical grain."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sales_analytics.analysis.insights import generate_insights
from sales_analytics.analysis.kpis import calculate_kpis, safe_ratio
from sales_analytics.pipeline.generate import GenerationConfig, generate_sales_data
from sales_analytics.pipeline.transform import WarehouseFrames, transform_sales


@pytest.fixture(scope="module")
def warehouse() -> WarehouseFrames:
    raw = generate_sales_data(
        GenerationConfig(number_of_rows=5_000, number_of_customers=600)
    )
    return transform_sales(raw)


@pytest.fixture(scope="module")
def results(warehouse: WarehouseFrames):
    return calculate_kpis(warehouse)


def test_overview_reconciles_to_fact_measures(warehouse, results) -> None:
    facts = warehouse.fact_sales
    assert results.overview["total_revenue"] == pytest.approx(
        float(facts["revenue"].sum())
    )
    assert results.overview["total_profit"] == pytest.approx(
        float(facts["profit"].sum())
    )
    assert results.overview["gross_margin"] == pytest.approx(
        float(facts["profit"].sum() / facts["revenue"].sum())
    )


def test_transactions_are_not_sales_lines(warehouse, results) -> None:
    distinct_orders = warehouse.fact_sales["transaction_id"].nunique()
    assert results.overview["transactions"] == distinct_orders
    assert distinct_orders < len(warehouse.fact_sales)
    assert results.overview["average_order_value"] == pytest.approx(
        results.overview["total_revenue"] / distinct_orders
    )


def test_customer_counts_and_repeat_rate(warehouse, results) -> None:
    facts = warehouse.fact_sales
    unique_customers = facts["customer_key"].nunique()
    orders = facts.groupby("customer_key")["transaction_id"].nunique()
    assert results.overview["unique_customers"] == unique_customers
    assert results.overview["repeat_customer_rate"] == pytest.approx(
        orders.ge(2).sum() / unique_customers
    )


def test_year_over_year_growth(results) -> None:
    annual = results.annual.sort_values("year", ignore_index=True)
    assert pd.isna(annual.loc[0, "revenue_yoy_growth"])
    expected = annual["revenue"].pct_change(fill_method=None)
    assert np.allclose(
        annual["revenue_yoy_growth"].iloc[1:], expected.iloc[1:], equal_nan=True
    )
    expected_profit = annual["profit"].pct_change(fill_method=None)
    assert np.allclose(
        annual["profit_yoy_growth"].iloc[1:],
        expected_profit.iloc[1:],
        equal_nan=True,
    )


def test_rankings_and_dimension_aggregations(results) -> None:
    assert results.products.iloc[0]["revenue"] == results.products["revenue"].max()
    assert (
        results.products.loc[results.products["profit_rank"].idxmin(), "profit"]
        == results.products["profit"].max()
    )
    assert (
        results.products.loc[results.products["bottom_profit_rank"].idxmin(), "profit"]
        == results.products["profit"].min()
    )
    assert (
        results.categories.loc[results.categories["revenue_rank"].idxmin(), "revenue"]
        == results.categories["revenue"].max()
    )
    assert (
        results.categories.loc[results.categories["profit_rank"].idxmin(), "profit"]
        == results.categories["profit"].max()
    )
    for frame in [results.categories, results.regions, results.channels]:
        assert frame["revenue"].sum() == pytest.approx(
            results.overview["total_revenue"]
        )
        assert frame["profit"].sum() == pytest.approx(results.overview["total_profit"])


def test_customer_concentration(results) -> None:
    top_10_revenue = results.customers.head(10)["lifetime_revenue"].sum()
    assert results.concentration["top_customer_revenue"] == pytest.approx(
        top_10_revenue
    )
    assert results.concentration["top_customer_revenue_share"] == pytest.approx(
        top_10_revenue / results.overview["total_revenue"]
    )


def test_zero_denominators_return_null() -> None:
    assert safe_ratio(10, 0) is None
    assert safe_ratio(0, 0) is None
    assert safe_ratio(10, 2) == 5


def test_kpi_outputs_are_deterministic(warehouse) -> None:
    first = calculate_kpis(warehouse)
    second = calculate_kpis(warehouse)
    assert first.overview == second.overview
    assert first.concentration == second.concentration
    for name in [
        "annual",
        "monthly",
        "products",
        "categories",
        "category_annual",
        "regions",
        "channels",
        "customers",
    ]:
        pd.testing.assert_frame_equal(getattr(first, name), getattr(second, name))


def test_insights_reference_calculated_conditions(results) -> None:
    insights = generate_insights(results)
    assert all(insight.condition and insight.evidence for insight in insights)
    assert len({insight.condition for insight in insights}) == len(insights)
