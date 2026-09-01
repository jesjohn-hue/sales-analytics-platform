"""Extract raw sales lines and enforce the source-column contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_REQUIRED_COLUMNS = [
    "transaction_id",
    "line_number",
    "order_date",
    "customer_id",
    "product_id",
    "product_name",
    "product_category",
    "unit_price",
    "quantity",
    "discount",
    "revenue",
    "unit_cost",
    "total_cost",
    "profit",
    "customer_region",
    "sales_channel",
]


class RawDataError(ValueError):
    """Raised when the raw sales file violates its expected contract."""


def read_raw_sales(path: str | Path) -> pd.DataFrame:
    """Read a raw sales CSV and fail clearly when required columns are absent."""
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Raw sales file not found: {source_path}")

    try:
        frame = pd.read_csv(
            source_path,
            dtype={
                "transaction_id": "string",
                "customer_id": "string",
                "product_id": "string",
            },
        )
    except (OSError, pd.errors.ParserError) as error:
        raise RawDataError(f"Unable to read raw sales file: {source_path}") from error

    missing_columns = sorted(set(RAW_REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise RawDataError(f"Raw sales file is missing required columns: {missing}")

    return frame.loc[:, RAW_REQUIRED_COLUMNS].copy()
