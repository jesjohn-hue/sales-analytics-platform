"""Transform raw sales lines into deterministic dimensional-model datasets."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from sales_analytics.pipeline.extract import RAW_REQUIRED_COLUMNS, RawDataError

MONEY_COLUMNS = ["unit_price", "revenue", "unit_cost", "total_cost", "profit"]
FACT_COLUMNS = [
    "sales_key",
    "transaction_id",
    "line_number",
    "date_key",
    "customer_key",
    "product_key",
    "channel_key",
    "quantity",
    "unit_price",
    "discount",
    "revenue",
    "unit_cost",
    "total_cost",
    "profit",
]


@dataclass(frozen=True)
class WarehouseFrames:
    """DataFrames ready to load in dependency-safe order."""

    dim_date: pd.DataFrame
    dim_customer: pd.DataFrame
    dim_category: pd.DataFrame
    dim_product: pd.DataFrame
    dim_channel: pd.DataFrame
    fact_sales: pd.DataFrame

    def dimensions(self) -> dict[str, pd.DataFrame]:
        """Expose dimensions by their database table names."""
        return {
            "dim_date": self.dim_date,
            "dim_customer": self.dim_customer,
            "dim_category": self.dim_category,
            "dim_product": self.dim_product,
            "dim_channel": self.dim_channel,
        }


def _validate_source(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize types and enforce stable cross-row business relationships."""
    missing_columns = sorted(set(RAW_REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise RawDataError(
            "Cannot transform data missing required columns: "
            + ", ".join(missing_columns)
        )
    data = frame.loc[:, RAW_REQUIRED_COLUMNS].copy()
    if data.empty:
        raise RawDataError("Cannot transform an empty sales dataset")
    if data.isna().any().any():
        columns = data.columns[data.isna().any()].tolist()
        raise RawDataError(f"Required source values are null in: {', '.join(columns)}")
    if data.duplicated(["transaction_id", "line_number"]).any():
        raise RawDataError("Duplicate transaction_id and line_number values found")

    data["order_date"] = pd.to_datetime(data["order_date"], errors="coerce")
    if data["order_date"].isna().any():
        raise RawDataError("order_date contains invalid values")

    integer_columns = ["line_number", "quantity"]
    numeric_columns = [*MONEY_COLUMNS, "discount"]
    try:
        for column in integer_columns:
            data[column] = pd.to_numeric(data[column], errors="raise").astype("int64")
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="raise")
    except (TypeError, ValueError) as error:
        raise RawDataError("Source numeric fields contain invalid values") from error

    if (data[["line_number", "quantity"]] <= 0).any().any():
        raise RawDataError("line_number and quantity must be positive")
    if (data[["unit_price", "unit_cost"]] <= 0).any().any():
        raise RawDataError("unit_price and unit_cost must be positive")
    if (data[["revenue", "total_cost"]] < 0).any().any():
        raise RawDataError("revenue and total_cost must be nonnegative")
    if not data["discount"].between(0, 1, inclusive="both").all():
        raise RawDataError("discount must be between 0 and 1")

    _require_financial_reconciliation(data)

    _require_stable_relationship(data, "customer_id", ["customer_region"])
    _require_stable_relationship(
        data, "product_id", ["product_name", "product_category"]
    )
    _require_stable_relationship(
        data,
        "transaction_id",
        ["order_date", "customer_id", "customer_region", "sales_channel"],
    )
    return data


def _require_stable_relationship(
    frame: pd.DataFrame, natural_key: str, attributes: list[str]
) -> None:
    counts = frame.groupby(natural_key, dropna=False)[attributes].nunique(dropna=False)
    if (counts > 1).any().any():
        unstable = counts.columns[(counts > 1).any()].tolist()
        raise RawDataError(
            f"{natural_key} maps to multiple values for: {', '.join(unstable)}"
        )


def _require_financial_reconciliation(frame: pd.DataFrame) -> None:
    cent = Decimal("0.01")

    def expected_values(row: pd.Series) -> tuple[Decimal, Decimal, Decimal]:
        unit_price = Decimal(str(row["unit_price"]))
        unit_cost = Decimal(str(row["unit_cost"]))
        quantity = int(row["quantity"])
        discount = Decimal(str(row["discount"]))
        revenue = (unit_price * quantity * (Decimal("1") - discount)).quantize(
            cent, rounding=ROUND_HALF_UP
        )
        total_cost = (unit_cost * quantity).quantize(cent, rounding=ROUND_HALF_UP)
        return revenue, total_cost, revenue - total_cost

    for _, row in frame.iterrows():
        expected_revenue, expected_cost, expected_profit = expected_values(row)
        observed = (
            Decimal(str(row["revenue"])).quantize(cent),
            Decimal(str(row["total_cost"])).quantize(cent),
            Decimal(str(row["profit"])).quantize(cent),
        )
        if observed != (expected_revenue, expected_cost, expected_profit):
            raise RawDataError(
                "Source revenue, total_cost, or profit fails financial reconciliation"
            )


def _build_date_dimension(dates: pd.Series) -> pd.DataFrame:
    calendar = pd.DataFrame(
        {"full_date": pd.date_range(dates.min(), dates.max(), freq="D")}
    )
    calendar["date_key"] = calendar["full_date"].dt.strftime("%Y%m%d").astype(int)
    calendar["day"] = calendar["full_date"].dt.day
    calendar["month"] = calendar["full_date"].dt.month
    calendar["month_name"] = calendar["full_date"].dt.month_name()
    calendar["quarter"] = calendar["full_date"].dt.quarter
    calendar["year"] = calendar["full_date"].dt.year
    calendar["day_of_week"] = calendar["full_date"].dt.day_name()
    calendar["is_weekend"] = calendar["full_date"].dt.dayofweek >= 5
    return calendar[
        [
            "date_key",
            "full_date",
            "day",
            "month",
            "month_name",
            "quarter",
            "year",
            "day_of_week",
            "is_weekend",
        ]
    ]


def _decimal_money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _decimal_rate(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0000"))


def transform_sales(frame: pd.DataFrame) -> WarehouseFrames:
    """Create deterministic dimension and fact datasets from raw sales lines."""
    data = _validate_source(frame)

    dim_date = _build_date_dimension(data["order_date"])
    dim_customer = (
        data[["customer_id", "customer_region"]]
        .drop_duplicates()
        .rename(columns={"customer_region": "region"})
        .sort_values("customer_id", ignore_index=True)
    )
    dim_customer.insert(0, "customer_key", range(1, len(dim_customer) + 1))

    dim_category = (
        data[["product_category"]]
        .drop_duplicates()
        .rename(columns={"product_category": "category_name"})
        .sort_values("category_name", ignore_index=True)
    )
    dim_category.insert(0, "category_key", range(1, len(dim_category) + 1))

    category_keys = dim_category.set_index("category_name")["category_key"]
    dim_product = (
        data[["product_id", "product_name", "product_category"]]
        .drop_duplicates()
        .sort_values("product_id", ignore_index=True)
    )
    dim_product["category_key"] = dim_product["product_category"].map(category_keys)
    dim_product = dim_product.drop(columns="product_category")
    dim_product.insert(0, "product_key", range(1, len(dim_product) + 1))

    dim_channel = (
        data[["sales_channel"]]
        .drop_duplicates()
        .rename(columns={"sales_channel": "channel_name"})
        .sort_values("channel_name", ignore_index=True)
    )
    dim_channel.insert(0, "channel_key", range(1, len(dim_channel) + 1))

    customer_keys = dim_customer.set_index("customer_id")["customer_key"]
    product_keys = dim_product.set_index("product_id")["product_key"]
    channel_keys = dim_channel.set_index("channel_name")["channel_key"]

    fact_sales = pd.DataFrame(
        {
            "transaction_id": data["transaction_id"],
            "line_number": data["line_number"],
            "date_key": data["order_date"].dt.strftime("%Y%m%d").astype(int),
            "customer_key": data["customer_id"].map(customer_keys),
            "product_key": data["product_id"].map(product_keys),
            "channel_key": data["sales_channel"].map(channel_keys),
            "quantity": data["quantity"],
            "unit_price": data["unit_price"].map(_decimal_money),
            "discount": data["discount"].map(_decimal_rate),
            "revenue": data["revenue"].map(_decimal_money),
            "unit_cost": data["unit_cost"].map(_decimal_money),
            "total_cost": data["total_cost"].map(_decimal_money),
            "profit": data["profit"].map(_decimal_money),
        }
    ).sort_values(["date_key", "transaction_id", "line_number"], ignore_index=True)
    fact_sales.insert(0, "sales_key", range(1, len(fact_sales) + 1))
    fact_sales = fact_sales[FACT_COLUMNS]

    warehouse = WarehouseFrames(
        dim_date=dim_date,
        dim_customer=dim_customer,
        dim_category=dim_category,
        dim_product=dim_product,
        dim_channel=dim_channel,
        fact_sales=fact_sales,
    )
    validate_warehouse_frames(warehouse)
    return warehouse


def validate_warehouse_frames(warehouse: WarehouseFrames) -> None:
    """Verify transformed keys and foreign-key coverage before persistence."""
    for name, dimension in warehouse.dimensions().items():
        if dimension.isna().any().any():
            raise RawDataError(f"Unexpected null values in {name}")
    if warehouse.fact_sales.isna().any().any():
        raise RawDataError("Unexpected null values in fact_sales")

    checks = {
        "date_key": set(warehouse.dim_date["date_key"]),
        "customer_key": set(warehouse.dim_customer["customer_key"]),
        "product_key": set(warehouse.dim_product["product_key"]),
        "channel_key": set(warehouse.dim_channel["channel_key"]),
    }
    for foreign_key, valid_keys in checks.items():
        if not set(warehouse.fact_sales[foreign_key]).issubset(valid_keys):
            raise RawDataError(f"fact_sales contains unresolved {foreign_key} values")
    if not set(warehouse.dim_product["category_key"]).issubset(
        set(warehouse.dim_category["category_key"])
    ):
        raise RawDataError("dim_product contains unresolved category_key values")
