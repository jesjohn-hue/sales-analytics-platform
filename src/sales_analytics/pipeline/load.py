"""Initialize and transactionally load the PostgreSQL dimensional warehouse."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import Connection, Cursor

from sales_analytics.config import Settings
from sales_analytics.pipeline.extract import read_raw_sales
from sales_analytics.pipeline.transform import WarehouseFrames, transform_sales


def _read_sql(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def initialize_schema(settings: Settings, connection: Connection | None = None) -> None:
    """Recreate all warehouse tables using the version-controlled DDL."""
    ddl = _read_sql(settings.schema_path)
    if connection is not None:
        connection.execute(ddl)
        return
    with psycopg.connect(settings.psycopg_dsn) as managed_connection:
        managed_connection.execute(ddl)


def _insert_rows(
    cursor: Cursor, table: str, columns: Sequence[str], frame: pd.DataFrame
) -> None:
    """Batch-insert a small dimension using psycopg's executemany pipeline."""
    column_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    statement = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    rows = (
        tuple(
            value.date() if isinstance(value, pd.Timestamp) else value for value in row
        )
        for row in frame.loc[:, columns].itertuples(index=False, name=None)
    )
    cursor.executemany(statement, rows)


def _copy_fact_sales(cursor: Cursor, fact_sales: pd.DataFrame) -> None:
    """Stream the large fact dataset with PostgreSQL COPY rather than INSERT rows."""
    columns = list(fact_sales.columns)
    copy_sql = f"COPY fact_sales ({', '.join(columns)}) FROM STDIN"
    with cursor.copy(copy_sql) as copy:
        for row in fact_sales.itertuples(index=False, name=None):
            copy.write_row(row)


def load_warehouse(
    warehouse: WarehouseFrames, settings: Settings, *, rebuild: bool = True
) -> None:
    """Load dimensions then facts atomically, optionally recreating the schema."""
    with psycopg.connect(settings.psycopg_dsn) as connection:
        with connection.transaction():
            if rebuild:
                initialize_schema(settings, connection)
            with connection.cursor() as cursor:
                _insert_rows(
                    cursor,
                    "dim_date",
                    list(warehouse.dim_date.columns),
                    warehouse.dim_date,
                )
                _insert_rows(
                    cursor,
                    "dim_customer",
                    list(warehouse.dim_customer.columns),
                    warehouse.dim_customer,
                )
                _insert_rows(
                    cursor,
                    "dim_category",
                    list(warehouse.dim_category.columns),
                    warehouse.dim_category,
                )
                _insert_rows(
                    cursor,
                    "dim_product",
                    list(warehouse.dim_product.columns),
                    warehouse.dim_product,
                )
                _insert_rows(
                    cursor,
                    "dim_channel",
                    list(warehouse.dim_channel.columns),
                    warehouse.dim_channel,
                )
                _copy_fact_sales(cursor, warehouse.fact_sales)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Raw sales CSV path")
    parser.add_argument(
        "--init-only", action="store_true", help="Recreate tables without loading data"
    )
    return parser.parse_args()


def main() -> None:
    """Initialize the schema or rebuild and load it from the raw sales CSV."""
    arguments = _parse_arguments()
    settings = Settings.from_env()
    if arguments.init_only:
        initialize_schema(settings)
        print(f"Initialized warehouse schema from {settings.schema_path}")
        return

    input_path = arguments.input or settings.raw_data_path
    raw_sales = read_raw_sales(input_path)
    warehouse = transform_sales(raw_sales)
    load_warehouse(warehouse, settings, rebuild=True)
    print(
        f"Loaded {len(warehouse.fact_sales):,} fact rows from {input_path} "
        f"into PostgreSQL"
    )


if __name__ == "__main__":
    main()
