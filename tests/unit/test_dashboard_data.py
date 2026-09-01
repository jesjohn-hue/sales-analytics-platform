"""Dashboard filtering tests at the validated fact grain."""

import pytest

from sales_analytics.analysis.kpis import calculate_kpis
from sales_analytics.dashboard.data import filter_options, filter_warehouse
from sales_analytics.pipeline.generate import GenerationConfig, generate_sales_data
from sales_analytics.pipeline.transform import transform_sales


@pytest.fixture(scope="module")
def warehouse():
    return transform_sales(
        generate_sales_data(
            GenerationConfig(number_of_rows=4_000, number_of_customers=500)
        )
    )


def test_default_filter_preserves_reconciled_headlines(warehouse) -> None:
    filtered = filter_warehouse(warehouse)
    assert calculate_kpis(filtered).overview == calculate_kpis(warehouse).overview
    assert len(filtered.fact_sales) == len(warehouse.fact_sales)


def test_filters_use_dimension_keys_without_changing_grain(warehouse) -> None:
    filtered = filter_warehouse(
        warehouse,
        years=[2025],
        regions=["West"],
        categories=["Technology"],
        channels=["Partner"],
    )
    assert not filtered.fact_sales.empty
    assert not filtered.fact_sales.duplicated(["transaction_id", "line_number"]).any()
    dates = filtered.fact_sales.merge(warehouse.dim_date, on="date_key")
    customers = filtered.fact_sales.merge(warehouse.dim_customer, on="customer_key")
    products = filtered.fact_sales.merge(warehouse.dim_product, on="product_key").merge(
        warehouse.dim_category, on="category_key"
    )
    channels = filtered.fact_sales.merge(warehouse.dim_channel, on="channel_key")
    assert set(dates["year"]) == {2025}
    assert set(customers["region"]) == {"West"}
    assert set(products["category_name"]) == {"Technology"}
    assert set(channels["channel_name"]) == {"Partner"}


def test_empty_selection_returns_empty_fact_set(warehouse) -> None:
    assert filter_warehouse(warehouse, years=[]).fact_sales.empty


def test_filter_options_match_dimensions(warehouse) -> None:
    options = filter_options(warehouse)
    assert options["years"] == [2023, 2024, 2025]
    assert options["regions"] == ["Midwest", "Northeast", "South", "West"]
    assert options["channels"] == ["Online", "Partner", "Retail"]
