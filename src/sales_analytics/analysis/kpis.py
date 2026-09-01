"""Canonical KPI calculations used to validate the SQL analysis layer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sales_analytics.pipeline.transform import WarehouseFrames


@dataclass(frozen=True)
class KPIResults:
    overview: dict[str, float | int | None]
    annual: pd.DataFrame
    monthly: pd.DataFrame
    products: pd.DataFrame
    categories: pd.DataFrame
    category_annual: pd.DataFrame
    regions: pd.DataFrame
    channels: pd.DataFrame
    customers: pd.DataFrame
    concentration: dict[str, float | int | None]


def safe_ratio(numerator: float, denominator: float) -> float | None:
    """Divide safely; undefined ratios remain null rather than becoming infinite."""
    return None if denominator == 0 else numerator / denominator


def enrich_sales(warehouse: WarehouseFrames) -> pd.DataFrame:
    """Join facts to descriptive dimensions at the unchanged sales-line grain."""
    facts = warehouse.fact_sales.copy()
    for column in [
        "unit_price",
        "discount",
        "revenue",
        "unit_cost",
        "total_cost",
        "profit",
    ]:
        facts[column] = facts[column].astype(float)
    products = warehouse.dim_product.merge(
        warehouse.dim_category, on="category_key", validate="many_to_one"
    )
    return (
        facts.merge(
            warehouse.dim_date[["date_key", "full_date", "year"]],
            on="date_key",
            validate="many_to_one",
        )
        .merge(warehouse.dim_customer, on="customer_key", validate="many_to_one")
        .merge(products, on="product_key", validate="many_to_one")
        .merge(warehouse.dim_channel, on="channel_key", validate="many_to_one")
    )


def _performance(data: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    grouped = data.groupby(groups, as_index=False, observed=True).agg(
        revenue=("revenue", "sum"),
        profit=("profit", "sum"),
        units_sold=("quantity", "sum"),
        transactions=("transaction_id", "nunique"),
        unique_customers=("customer_id", "nunique"),
    )
    grouped["gross_margin"] = np.where(
        grouped["revenue"].ne(0), grouped["profit"] / grouped["revenue"], np.nan
    )
    grouped["average_order_value"] = np.where(
        grouped["transactions"].ne(0),
        grouped["revenue"] / grouped["transactions"],
        np.nan,
    )
    return grouped


def _add_yoy(frame: pd.DataFrame, groups: list[str] | None = None) -> pd.DataFrame:
    result = frame.sort_values([*(groups or []), "year"]).copy()
    if groups:
        prior_revenue = result.groupby(groups)["revenue"].shift(1)
        prior_profit = result.groupby(groups)["profit"].shift(1)
    else:
        prior_revenue = result["revenue"].shift(1)
        prior_profit = result["profit"].shift(1)
    result["revenue_yoy_growth"] = np.where(
        prior_revenue.ne(0), (result["revenue"] - prior_revenue) / prior_revenue, np.nan
    )
    result["profit_yoy_growth"] = np.where(
        prior_profit.ne(0), (result["profit"] - prior_profit) / prior_profit, np.nan
    )
    return result


def calculate_kpis(
    warehouse: WarehouseFrames, *, top_customer_count: int = 10
) -> KPIResults:
    """Calculate the portfolio's canonical KPI set from transformed data."""
    data = enrich_sales(warehouse)
    total_revenue = float(data["revenue"].sum())
    total_profit = float(data["profit"].sum())
    transactions = int(data["transaction_id"].nunique())
    unique_customers = int(data["customer_id"].nunique())
    customer_orders = data.groupby("customer_id")["transaction_id"].nunique()
    repeat_customers = int(customer_orders.ge(2).sum())
    overview = {
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "gross_margin": safe_ratio(total_profit, total_revenue),
        "transactions": transactions,
        "units_sold": int(data["quantity"].sum()),
        "average_order_value": safe_ratio(total_revenue, transactions),
        "average_revenue_per_customer": safe_ratio(total_revenue, unique_customers),
        "unique_customers": unique_customers,
        "repeat_customers": repeat_customers,
        "repeat_customer_rate": safe_ratio(repeat_customers, unique_customers),
    }

    annual = _add_yoy(_performance(data, ["year"]))
    monthly_data = data.assign(
        month=data["full_date"].dt.to_period("M").dt.to_timestamp()
    )
    monthly = _performance(monthly_data, ["month"]).sort_values(
        "month", ignore_index=True
    )

    products = _performance(data, ["product_id", "product_name", "category_name"])
    products["revenue_rank"] = (
        products["revenue"].rank(method="dense", ascending=False).astype(int)
    )
    products["profit_rank"] = (
        products["profit"].rank(method="dense", ascending=False).astype(int)
    )
    products["bottom_profit_rank"] = (
        products["profit"].rank(method="dense", ascending=True).astype(int)
    )
    products = products.sort_values("revenue_rank", ignore_index=True)

    categories = _performance(data, ["category_name"])
    category_year = _add_yoy(
        _performance(data, ["category_name", "year"]), ["category_name"]
    )
    categories = categories.merge(
        category_year.groupby("category_name", as_index=False).tail(1)[
            ["category_name", "revenue_yoy_growth", "profit_yoy_growth"]
        ],
        on="category_name",
        how="left",
        validate="one_to_one",
    )
    categories["revenue_rank"] = (
        categories["revenue"].rank(method="dense", ascending=False).astype(int)
    )
    categories["profit_rank"] = (
        categories["profit"].rank(method="dense", ascending=False).astype(int)
    )
    categories = categories.sort_values("revenue_rank", ignore_index=True)

    regions = _performance(data, ["region"])
    region_year = _add_yoy(_performance(data, ["region", "year"]), ["region"])
    regions = regions.merge(
        region_year.groupby("region", as_index=False).tail(1)[
            ["region", "revenue_yoy_growth", "profit_yoy_growth"]
        ],
        on="region",
        how="left",
        validate="one_to_one",
    ).sort_values("revenue", ascending=False, ignore_index=True)

    channels = _performance(data, ["channel_name"]).sort_values(
        "revenue", ascending=False, ignore_index=True
    )
    customers = (
        _performance(data, ["customer_id", "region"])
        .rename(columns={"revenue": "lifetime_revenue", "profit": "lifetime_profit"})
        .sort_values("lifetime_revenue", ascending=False, ignore_index=True)
    )
    top_count = min(max(top_customer_count, 0), len(customers))
    top_revenue = float(customers.head(top_count)["lifetime_revenue"].sum())
    concentration = {
        "top_customer_count": top_count,
        "top_customer_revenue": top_revenue,
        "top_customer_revenue_share": safe_ratio(top_revenue, total_revenue),
    }
    return KPIResults(
        overview,
        annual,
        monthly,
        products,
        categories,
        category_year.reset_index(drop=True),
        regions,
        channels,
        customers,
        concentration,
    )
