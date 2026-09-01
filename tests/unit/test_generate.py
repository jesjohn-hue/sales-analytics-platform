"""Data-contract and business-rule tests for synthetic sales generation."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
import pytest

from sales_analytics.pipeline.generate import (
    CHANNEL_BASE_WEIGHTS,
    PRODUCTS,
    REGION_BASE_WEIGHTS,
    REQUIRED_COLUMNS,
    GenerationConfig,
    generate_sales_data,
)


@pytest.fixture(scope="module")
def sales_data() -> pd.DataFrame:
    """Use a representative sample while keeping the unit suite fast."""
    return generate_sales_data(
        GenerationConfig(number_of_rows=8_000, number_of_customers=900)
    )


def test_output_shape_and_required_values(sales_data: pd.DataFrame) -> None:
    assert list(sales_data.columns) == REQUIRED_COLUMNS
    assert len(sales_data) == 8_000
    assert not sales_data.isna().any().any()
    assert not sales_data.select_dtypes(include="object").eq("").any().any()


def test_revenue_calculation(sales_data: pd.DataFrame) -> None:
    def expected_revenue(row: pd.Series) -> float:
        amount = (
            Decimal(str(row["unit_price"]))
            * int(row["quantity"])
            * (Decimal("1") - Decimal(str(row["discount"])))
        )
        return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    expected = sales_data.apply(expected_revenue, axis=1)
    assert np.array_equal(sales_data["revenue"].to_numpy(), expected.to_numpy())


def test_cost_and_profit_calculations(sales_data: pd.DataFrame) -> None:
    expected_cost = (sales_data["unit_cost"] * sales_data["quantity"]).round(2)
    expected_profit = (sales_data["revenue"] - sales_data["total_cost"]).round(2)
    assert np.allclose(sales_data["total_cost"], expected_cost, atol=0.005)
    assert np.allclose(sales_data["profit"], expected_profit, atol=0.005)
    assert (sales_data[["unit_cost", "total_cost"]] >= 0).all().all()


def test_numeric_business_ranges(sales_data: pd.DataFrame) -> None:
    assert (sales_data["quantity"] > 0).all()
    assert (sales_data["unit_price"] > 0).all()
    assert sales_data["discount"].between(0, 0.30, inclusive="both").all()
    assert (sales_data["revenue"] >= 0).all()


def test_dates_fall_within_configured_period(sales_data: pd.DataFrame) -> None:
    dates = pd.to_datetime(sales_data["order_date"])
    assert dates.min() >= pd.Timestamp("2023-01-01")
    assert dates.max() <= pd.Timestamp("2025-12-31")


def test_identifiers_and_sales_line_grain(sales_data: pd.DataFrame) -> None:
    assert (
        sales_data["transaction_id"]
        .map(lambda value: bool(re.fullmatch(r"TXN\d{7}", value)))
        .all()
    )
    assert (
        sales_data["customer_id"]
        .map(lambda value: bool(re.fullmatch(r"CUST\d{5}", value)))
        .all()
    )
    assert (
        sales_data["product_id"]
        .map(lambda value: bool(re.fullmatch(r"PROD\d{3}", value)))
        .all()
    )
    assert not sales_data.duplicated(["transaction_id", "line_number"]).any()
    assert (sales_data["line_number"] > 0).all()


def test_product_master_relationships_are_consistent(sales_data: pd.DataFrame) -> None:
    expected = {
        product.product_id: (product.name, product.category) for product in PRODUCTS
    }
    observed = sales_data.groupby("product_id")[["product_name", "product_category"]]
    assert (observed.nunique() == 1).all().all()
    actual = (
        sales_data[["product_id", "product_name", "product_category"]]
        .drop_duplicates()
        .set_index("product_id")
    )
    assert {
        product_id: (row.product_name, row.product_category)
        for product_id, row in actual.iterrows()
    } == expected


def test_transaction_attributes_are_internally_consistent(
    sales_data: pd.DataFrame,
) -> None:
    transaction_attributes = sales_data.groupby("transaction_id")[
        ["order_date", "customer_id", "customer_region", "sales_channel"]
    ].nunique()
    assert (transaction_attributes == 1).all().all()
    products_per_transaction = sales_data.groupby("transaction_id")[
        "product_id"
    ].nunique()
    lines_per_transaction = sales_data.groupby("transaction_id").size()
    assert products_per_transaction.equals(lines_per_transaction)


def test_customers_have_one_region_and_repeat_customers_exist(
    sales_data: pd.DataFrame,
) -> None:
    assert (sales_data.groupby("customer_id")["customer_region"].nunique() == 1).all()
    customer_orders = sales_data.groupby("customer_id")["transaction_id"].nunique()
    assert (customer_orders >= 2).any()
    assert (customer_orders >= 2).mean() > 0.25


def test_controlled_vocabularies_and_catalog_coverage(sales_data: pd.DataFrame) -> None:
    assert set(sales_data["customer_region"]) == set(REGION_BASE_WEIGHTS)
    assert set(sales_data["sales_channel"]) == set(CHANNEL_BASE_WEIGHTS)
    assert set(sales_data["product_id"]) == {product.product_id for product in PRODUCTS}


def test_margin_structure_varies_by_product(sales_data: pd.DataFrame) -> None:
    product_margin = sales_data.groupby("product_id").apply(
        lambda rows: rows["profit"].sum() / rows["revenue"].sum(),
        include_groups=False,
    )
    assert product_margin.max() - product_margin.min() > 0.20


def test_generation_is_reproducible() -> None:
    config = GenerationConfig(
        number_of_rows=500, number_of_customers=100, random_seed=7
    )
    first = generate_sales_data(config)
    second = generate_sales_data(config)
    pd.testing.assert_frame_equal(first, second)


def test_custom_date_period_is_respected() -> None:
    frame = generate_sales_data(
        GenerationConfig(
            start_date="2020-06-01",
            end_date="2021-05-31",
            number_of_rows=300,
            number_of_customers=75,
        )
    )
    dates = pd.to_datetime(frame["order_date"])
    assert dates.min() >= pd.Timestamp("2020-06-01")
    assert dates.max() <= pd.Timestamp("2021-05-31")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start_date": "2025-01-02", "end_date": "2025-01-01"}, "start_date"),
        ({"number_of_rows": 0}, "number_of_rows"),
        ({"number_of_customers": 0}, "number_of_customers"),
    ],
)
def test_invalid_configuration_is_rejected(changes: dict, message: str) -> None:
    values = {
        "start_date": "2023-01-01",
        "end_date": "2025-12-31",
        "number_of_rows": 100,
        "number_of_customers": 20,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        generate_sales_data(GenerationConfig(**values))
