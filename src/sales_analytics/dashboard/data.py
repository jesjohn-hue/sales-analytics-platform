"""Filter validated warehouse frames without redefining KPI calculations."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from sales_analytics.pipeline.transform import WarehouseFrames


def filter_warehouse(
    warehouse: WarehouseFrames,
    *,
    years: list[int] | None = None,
    regions: list[str] | None = None,
    categories: list[str] | None = None,
    channels: list[str] | None = None,
) -> WarehouseFrames:
    """Filter fact rows through conformed dimensions while preserving their grain."""
    facts = warehouse.fact_sales
    mask = pd.Series(True, index=facts.index)
    if years is not None:
        date_keys = set(
            warehouse.dim_date.loc[warehouse.dim_date["year"].isin(years), "date_key"]
        )
        mask &= facts["date_key"].isin(date_keys)
    if regions is not None:
        customer_keys = set(
            warehouse.dim_customer.loc[
                warehouse.dim_customer["region"].isin(regions), "customer_key"
            ]
        )
        mask &= facts["customer_key"].isin(customer_keys)
    if categories is not None:
        category_keys = set(
            warehouse.dim_category.loc[
                warehouse.dim_category["category_name"].isin(categories),
                "category_key",
            ]
        )
        product_keys = set(
            warehouse.dim_product.loc[
                warehouse.dim_product["category_key"].isin(category_keys),
                "product_key",
            ]
        )
        mask &= facts["product_key"].isin(product_keys)
    if channels is not None:
        channel_keys = set(
            warehouse.dim_channel.loc[
                warehouse.dim_channel["channel_name"].isin(channels), "channel_key"
            ]
        )
        mask &= facts["channel_key"].isin(channel_keys)
    return replace(warehouse, fact_sales=facts.loc[mask].reset_index(drop=True))


def filter_options(warehouse: WarehouseFrames) -> dict[str, list]:
    """Return sorted global filter values from the conformed dimensions."""
    return {
        "years": sorted(warehouse.dim_date["year"].unique().tolist()),
        "regions": sorted(warehouse.dim_customer["region"].unique().tolist()),
        "categories": sorted(warehouse.dim_category["category_name"].unique().tolist()),
        "channels": sorted(warehouse.dim_channel["channel_name"].unique().tolist()),
    }
