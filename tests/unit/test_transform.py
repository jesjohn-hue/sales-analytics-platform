"""Unit tests for extraction and deterministic dimensional transformation."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from sales_analytics.pipeline.extract import RawDataError, read_raw_sales
from sales_analytics.pipeline.generate import GenerationConfig, generate_sales_data
from sales_analytics.pipeline.transform import WarehouseFrames, transform_sales


@pytest.fixture(scope="module")
def raw_sales() -> pd.DataFrame:
    return generate_sales_data(
        GenerationConfig(number_of_rows=2_000, number_of_customers=300)
    )


@pytest.fixture(scope="module")
def warehouse(raw_sales: pd.DataFrame) -> WarehouseFrames:
    return transform_sales(raw_sales)


def test_extract_rejects_missing_required_columns(tmp_path) -> None:
    path = tmp_path / "missing.csv"
    pd.DataFrame({"transaction_id": ["TXN0000001"]}).to_csv(path, index=False)
    with pytest.raises(RawDataError, match="missing required columns"):
        read_raw_sales(path)


def test_extract_reads_expected_columns(raw_sales: pd.DataFrame, tmp_path) -> None:
    path = tmp_path / "sales.csv"
    raw_sales.to_csv(path, index=False)
    extracted = read_raw_sales(path)
    assert len(extracted) == len(raw_sales)
    assert list(extracted.columns) == list(raw_sales.columns)


def test_raw_row_count_equals_fact_row_count(
    raw_sales: pd.DataFrame, warehouse: WarehouseFrames
) -> None:
    assert len(warehouse.fact_sales) == len(raw_sales)
    assert not warehouse.fact_sales.duplicated(["transaction_id", "line_number"]).any()


def test_natural_dimension_identifiers_are_unique(
    warehouse: WarehouseFrames,
) -> None:
    assert warehouse.dim_date["full_date"].is_unique
    assert warehouse.dim_customer["customer_id"].is_unique
    assert warehouse.dim_category["category_name"].is_unique
    assert warehouse.dim_product["product_id"].is_unique
    assert warehouse.dim_channel["channel_name"].is_unique


def test_every_fact_foreign_key_resolves(warehouse: WarehouseFrames) -> None:
    valid_keys = {
        "date_key": set(warehouse.dim_date["date_key"]),
        "customer_key": set(warehouse.dim_customer["customer_key"]),
        "product_key": set(warehouse.dim_product["product_key"]),
        "channel_key": set(warehouse.dim_channel["channel_key"]),
    }
    for foreign_key, dimension_keys in valid_keys.items():
        assert set(warehouse.fact_sales[foreign_key]) <= dimension_keys
    assert set(warehouse.dim_product["category_key"]) <= set(
        warehouse.dim_category["category_key"]
    )


def test_product_category_relationships_are_preserved(
    raw_sales: pd.DataFrame, warehouse: WarehouseFrames
) -> None:
    observed = warehouse.dim_product.merge(
        warehouse.dim_category, on="category_key", validate="many_to_one"
    )[["product_id", "product_name", "category_name"]].rename(
        columns={"category_name": "product_category"}
    )
    expected = raw_sales[
        ["product_id", "product_name", "product_category"]
    ].drop_duplicates()
    pd.testing.assert_frame_equal(
        observed.sort_values("product_id", ignore_index=True),
        expected.sort_values("product_id", ignore_index=True),
    )


def test_customer_region_relationships_are_preserved(
    raw_sales: pd.DataFrame, warehouse: WarehouseFrames
) -> None:
    expected = raw_sales[["customer_id", "customer_region"]].drop_duplicates()
    observed = warehouse.dim_customer[["customer_id", "region"]].rename(
        columns={"region": "customer_region"}
    )
    pd.testing.assert_frame_equal(
        observed.sort_values("customer_id", ignore_index=True),
        expected.sort_values("customer_id", ignore_index=True),
    )


def test_date_keys_map_to_correct_dates(warehouse: WarehouseFrames) -> None:
    expected_keys = warehouse.dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    assert warehouse.dim_date["date_key"].equals(expected_keys)
    assert warehouse.dim_date["is_weekend"].equals(
        warehouse.dim_date["full_date"].dt.dayofweek >= 5
    )


def test_financial_values_survive_transformation(
    raw_sales: pd.DataFrame, warehouse: WarehouseFrames
) -> None:
    source = raw_sales.set_index(["transaction_id", "line_number"])
    facts = warehouse.fact_sales.set_index(["transaction_id", "line_number"])
    for column in ["unit_price", "revenue", "unit_cost", "total_cost", "profit"]:
        expected = source[column].map(
            lambda value: Decimal(str(value)).quantize(Decimal("0.01"))
        )
        assert facts[column].equals(expected.loc[facts.index])
    expected_discount = source["discount"].map(
        lambda value: Decimal(str(value)).quantize(Decimal("0.0000"))
    )
    assert facts["discount"].equals(expected_discount.loc[facts.index])


def test_no_unexpected_nulls(warehouse: WarehouseFrames) -> None:
    for frame in [*warehouse.dimensions().values(), warehouse.fact_sales]:
        assert not frame.isna().any().any()


def test_transaction_context_is_preserved(
    raw_sales: pd.DataFrame, warehouse: WarehouseFrames
) -> None:
    facts = (
        warehouse.fact_sales.merge(
            warehouse.dim_date[["date_key", "full_date"]], on="date_key"
        )
        .merge(
            warehouse.dim_customer[["customer_key", "customer_id"]],
            on="customer_key",
        )
        .merge(warehouse.dim_channel[["channel_key", "channel_name"]], on="channel_key")
    )
    expected = raw_sales.groupby("transaction_id")[
        ["order_date", "customer_id", "sales_channel"]
    ].first()
    observed = (
        facts.groupby("transaction_id")[["full_date", "customer_id", "channel_name"]]
        .first()
        .rename(columns={"full_date": "order_date", "channel_name": "sales_channel"})
    )
    expected["order_date"] = pd.to_datetime(expected["order_date"])
    pd.testing.assert_frame_equal(observed, expected.loc[observed.index])


def test_transformation_is_deterministic(raw_sales: pd.DataFrame) -> None:
    first = transform_sales(raw_sales)
    second = transform_sales(raw_sales.sample(frac=1, random_state=9))
    for field_name in WarehouseFrames.__dataclass_fields__:
        first_frame = getattr(first, field_name)
        second_frame = getattr(second, field_name)
        pd.testing.assert_frame_equal(first_frame, second_frame)


def test_unstable_customer_region_is_rejected(raw_sales: pd.DataFrame) -> None:
    invalid = raw_sales.copy()
    customer_id = invalid.loc[0, "customer_id"]
    matching_rows = invalid.index[invalid["customer_id"] == customer_id]
    invalid.loc[matching_rows[0], "customer_region"] = "Invalid Region"
    with pytest.raises(RawDataError, match="customer_id maps to multiple values"):
        transform_sales(invalid)


def test_financial_mismatch_is_rejected(raw_sales: pd.DataFrame) -> None:
    invalid = raw_sales.copy()
    invalid.loc[0, "revenue"] += 1
    with pytest.raises(RawDataError, match="financial reconciliation"):
        transform_sales(invalid)
