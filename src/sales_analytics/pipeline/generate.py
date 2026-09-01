"""Generate reproducible, business-realistic synthetic sales data.

The output represents sales-line records. Rows within a transaction share the
same date, customer, region, and channel but may contain different products.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
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

REGION_BASE_WEIGHTS = {
    "Midwest": 0.17,
    "Northeast": 0.24,
    "South": 0.29,
    "West": 0.30,
}
REGION_ANNUAL_TRENDS = {
    "Midwest": 0.98,
    "Northeast": 1.02,
    "South": 1.04,
    "West": 1.15,
}
CHANNEL_BASE_WEIGHTS = {"Online": 0.54, "Partner": 0.14, "Retail": 0.32}
MONTHLY_SEASONALITY = {
    1: 0.82,
    2: 0.86,
    3: 0.96,
    4: 1.00,
    5: 1.03,
    6: 1.06,
    7: 0.95,
    8: 1.00,
    9: 1.08,
    10: 1.16,
    11: 1.42,
    12: 1.55,
}
CATEGORY_ANNUAL_TRENDS = {
    "Accessories": 1.12,
    "Furniture": 1.01,
    "Office Supplies": 0.87,
    "Technology": 1.14,
}


@dataclass(frozen=True)
class GenerationConfig:
    """Configuration that fully determines a generated dataset."""

    start_date: str = "2023-01-01"
    end_date: str = "2025-12-31"
    number_of_rows: int = 50_000
    number_of_customers: int = 4_500
    random_seed: int = 42
    output_path: Path = Path("data/raw/sales.csv")

    def validate(self) -> None:
        """Reject invalid configurations before generation starts."""
        start = pd.Timestamp(self.start_date)
        end = pd.Timestamp(self.end_date)
        if start > end:
            raise ValueError("start_date must be on or before end_date")
        if self.number_of_rows < 1:
            raise ValueError("number_of_rows must be positive")
        if self.number_of_customers < 1:
            raise ValueError("number_of_customers must be positive")


@dataclass(frozen=True)
class Product:
    """Stable product master data plus a relative demand multiplier."""

    product_id: str
    name: str
    category: str
    base_price: float
    cost_ratio: float
    demand_weight: float


PRODUCTS = (
    Product("PROD001", "Apex Pro Laptop", "Technology", 1_299.00, 0.86, 1.35),
    Product("PROD002", "Apex Standard Laptop", "Technology", 899.00, 0.72, 1.15),
    Product("PROD003", "Core Business Desktop", "Technology", 1_049.00, 0.70, 0.75),
    Product("PROD004", "Compact Business Tablet", "Technology", 579.00, 0.64, 0.90),
    Product("PROD005", "27-inch QHD Monitor", "Technology", 349.00, 0.58, 1.10),
    Product("PROD006", "24-inch Office Monitor", "Technology", 219.00, 0.60, 1.25),
    Product("PROD007", "Wireless Keyboard", "Accessories", 69.00, 0.42, 1.40),
    Product("PROD008", "Ergonomic Mouse", "Accessories", 49.00, 0.38, 1.55),
    Product("PROD009", "USB-C Docking Station", "Accessories", 189.00, 0.55, 1.20),
    Product("PROD010", "Noise-Canceling Headset", "Accessories", 159.00, 0.48, 1.05),
    Product("PROD011", "Laptop Carrying Case", "Accessories", 59.00, 0.36, 0.95),
    Product("PROD012", "HD Webcam", "Accessories", 89.00, 0.44, 1.10),
    Product("PROD013", "Executive Desk", "Furniture", 749.00, 0.61, 0.60),
    Product("PROD014", "Adjustable Standing Desk", "Furniture", 629.00, 0.57, 0.85),
    Product("PROD015", "Ergonomic Office Chair", "Furniture", 459.00, 0.54, 1.00),
    Product("PROD016", "Mobile Filing Cabinet", "Furniture", 219.00, 0.59, 0.65),
    Product("PROD017", "Conference Table", "Furniture", 999.00, 0.67, 0.38),
    Product("PROD018", "Bookshelf", "Furniture", 189.00, 0.52, 0.58),
    Product("PROD019", "Premium Printer Paper", "Office Supplies", 39.00, 0.56, 1.45),
    Product("PROD020", "Recycled Printer Paper", "Office Supplies", 31.00, 0.52, 1.30),
    Product(
        "PROD021", "Ink Cartridge Multipack", "Office Supplies", 109.00, 0.62, 1.15
    ),
    Product("PROD022", "Desktop Organizer", "Office Supplies", 34.00, 0.43, 0.85),
    Product("PROD023", "Business Notebook Pack", "Office Supplies", 27.00, 0.41, 1.10),
    Product("PROD024", "Shipping Label Pack", "Office Supplies", 24.00, 0.46, 0.90),
)


def _money(value: float | Decimal) -> float:
    """Round a monetary value to cents using conventional business rounding."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_customer_pools(
    config: GenerationConfig, rng: np.random.Generator
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Create fixed customer-region relationships and varied purchase frequency."""
    regions = np.array(list(REGION_BASE_WEIGHTS))
    region_probabilities = np.array(list(REGION_BASE_WEIGHTS.values()))
    customer_regions = rng.choice(
        regions, size=config.number_of_customers, p=region_probabilities
    )
    customer_ids = np.array(
        [f"CUST{number:05d}" for number in range(1, config.number_of_customers + 1)]
    )

    # A long-tailed propensity creates occasional buyers and a small valuable core.
    propensities = rng.pareto(1.9, size=config.number_of_customers) + 0.15
    valuable_customer_count = max(1, config.number_of_customers // 20)
    valuable_indices = np.argpartition(propensities, -valuable_customer_count)[
        -valuable_customer_count:
    ]
    propensities[valuable_indices] *= 2.5

    pools = {}
    for region in regions:
        mask = customer_regions == region
        regional_propensities = propensities[mask]
        pools[str(region)] = (
            customer_ids[mask],
            regional_propensities / regional_propensities.sum(),
        )
    return pools


def _date_probabilities(
    config: GenerationConfig,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Return daily probabilities with seasonality and overall annual growth."""
    dates = pd.date_range(config.start_date, config.end_date, freq="D")
    elapsed_years = dates.year - dates.year.min()
    weights = np.array([MONTHLY_SEASONALITY[month] for month in dates.month])
    weights *= np.power(1.08, elapsed_years)
    return dates, weights / weights.sum()


def _choose_region(
    order_date: pd.Timestamp, base_year: int, rng: np.random.Generator
) -> str:
    """Choose a region while allowing regional sales mix to change over time."""
    years_elapsed = order_date.year - base_year
    regions = np.array(list(REGION_BASE_WEIGHTS))
    weights = np.array(
        [
            REGION_BASE_WEIGHTS[region] * REGION_ANNUAL_TRENDS[region] ** years_elapsed
            for region in regions
        ]
    )
    return str(rng.choice(regions, p=weights / weights.sum()))


def _choose_channel(rng: np.random.Generator) -> str:
    channels = np.array(list(CHANNEL_BASE_WEIGHTS))
    return str(rng.choice(channels, p=list(CHANNEL_BASE_WEIGHTS.values())))


def _line_count(channel: str, rng: np.random.Generator) -> int:
    """Partner orders contain more product lines and therefore higher AOV."""
    choices = np.array([1, 2, 3, 4])
    probabilities = {
        "Online": [0.67, 0.23, 0.08, 0.02],
        "Retail": [0.73, 0.20, 0.06, 0.01],
        "Partner": [0.31, 0.35, 0.23, 0.11],
    }
    return int(rng.choice(choices, p=probabilities[channel]))


def _choose_products(
    order_date: pd.Timestamp,
    base_year: int,
    count: int,
    rng: np.random.Generator,
) -> list[Product]:
    """Choose distinct products using stable demand plus category-level trends."""
    years_elapsed = order_date.year - base_year
    weights = np.array(
        [
            product.demand_weight
            * CATEGORY_ANNUAL_TRENDS[product.category] ** years_elapsed
            for product in PRODUCTS
        ]
    )
    indices = rng.choice(
        len(PRODUCTS), size=count, replace=False, p=weights / weights.sum()
    )
    return [PRODUCTS[int(index)] for index in indices]


def _quantity(channel: str, product: Product, rng: np.random.Generator) -> int:
    """Sample positive quantities informed by channel and product type."""
    if channel == "Partner":
        quantity = int(
            rng.choice(
                [2, 3, 4, 5, 6, 8, 10], p=[0.16, 0.20, 0.20, 0.16, 0.12, 0.10, 0.06]
            )
        )
    else:
        quantity = int(rng.choice([1, 2, 3, 4, 5], p=[0.67, 0.20, 0.08, 0.03, 0.02]))
    if product.category == "Office Supplies":
        quantity += int(rng.choice([0, 1, 2, 4], p=[0.55, 0.24, 0.15, 0.06]))
    return quantity


def _discount(channel: str, rng: np.random.Generator) -> float:
    """Sample a sensible discount rate with larger partner-order discounts."""
    options = np.array([0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
    probabilities = {
        "Online": [0.40, 0.22, 0.18, 0.11, 0.06, 0.02, 0.01],
        "Retail": [0.53, 0.20, 0.14, 0.08, 0.04, 0.01, 0.00],
        "Partner": [0.08, 0.14, 0.22, 0.23, 0.18, 0.10, 0.05],
    }
    return float(rng.choice(options, p=probabilities[channel]))


def generate_sales_data(config: GenerationConfig | None = None) -> pd.DataFrame:
    """Generate sales-line records deterministically for a given configuration."""
    config = config or GenerationConfig()
    config.validate()
    rng = np.random.default_rng(config.random_seed)
    customer_pools = _build_customer_pools(config, rng)
    dates, date_probabilities = _date_probabilities(config)
    base_year = pd.Timestamp(config.start_date).year
    records: list[dict[str, object]] = []
    transaction_number = 1

    while len(records) < config.number_of_rows:
        order_date = pd.Timestamp(rng.choice(dates, p=date_probabilities))
        region = _choose_region(order_date, base_year, rng)
        customer_ids, customer_probabilities = customer_pools[region]
        customer_id = str(rng.choice(customer_ids, p=customer_probabilities))
        channel = _choose_channel(rng)
        lines_remaining = config.number_of_rows - len(records)
        number_of_lines = min(_line_count(channel, rng), lines_remaining)
        products = _choose_products(order_date, base_year, number_of_lines, rng)
        transaction_id = f"TXN{transaction_number:07d}"

        for line_number, product in enumerate(products, start=1):
            unit_price = round(product.base_price * rng.uniform(0.97, 1.04), 2)
            unit_cost = round(
                product.base_price * product.cost_ratio * rng.uniform(0.98, 1.02), 2
            )
            quantity = _quantity(channel, product, rng)
            discount = _discount(channel, rng)
            revenue = _money(
                Decimal(str(unit_price))
                * quantity
                * (Decimal("1") - Decimal(str(discount)))
            )
            total_cost = _money(Decimal(str(unit_cost)) * quantity)
            profit = _money(Decimal(str(revenue)) - Decimal(str(total_cost)))

            records.append(
                {
                    "transaction_id": transaction_id,
                    "line_number": line_number,
                    "order_date": order_date.date().isoformat(),
                    "customer_id": customer_id,
                    "product_id": product.product_id,
                    "product_name": product.name,
                    "product_category": product.category,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "discount": discount,
                    "revenue": revenue,
                    "unit_cost": unit_cost,
                    "total_cost": total_cost,
                    "profit": profit,
                    "customer_region": region,
                    "sales_channel": channel,
                }
            )
        transaction_number += 1

    frame = pd.DataFrame.from_records(records, columns=REQUIRED_COLUMNS)
    return frame.sort_values(
        ["order_date", "transaction_id", "line_number"], ignore_index=True
    )


def write_sales_data(
    frame: pd.DataFrame, output_path: str | Path = GenerationConfig.output_path
) -> Path:
    """Write generated data to CSV and return the resolved output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, date_format="%Y-%m-%d")
    return path.resolve()


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=GenerationConfig.output_path)
    parser.add_argument("--rows", type=int, default=GenerationConfig.number_of_rows)
    parser.add_argument(
        "--customers", type=int, default=GenerationConfig.number_of_customers
    )
    parser.add_argument("--seed", type=int, default=GenerationConfig.random_seed)
    parser.add_argument("--start-date", default=GenerationConfig.start_date)
    parser.add_argument("--end-date", default=GenerationConfig.end_date)
    return parser.parse_args()


def main() -> None:
    """Generate and write a dataset using command-line configuration."""
    arguments = _parse_arguments()
    config = GenerationConfig(
        start_date=arguments.start_date,
        end_date=arguments.end_date,
        number_of_rows=arguments.rows,
        number_of_customers=arguments.customers,
        random_seed=arguments.seed,
        output_path=arguments.output,
    )
    frame = generate_sales_data(config)
    path = write_sales_data(frame, config.output_path)
    print(
        f"Generated {len(frame):,} sales lines from "
        f"{frame['order_date'].min()} through {frame['order_date'].max()} at {path}"
    )


if __name__ == "__main__":
    main()
