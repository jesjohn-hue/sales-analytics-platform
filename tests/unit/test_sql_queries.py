"""Lightweight static checks for version-controlled PostgreSQL analysis SQL."""

from pathlib import Path

QUERY_DIRECTORY = Path("sql/queries")
EXPECTED_FILES = {
    "01_executive_summary.sql",
    "02_revenue_trends.sql",
    "03_product_performance.sql",
    "04_region_performance.sql",
    "05_channel_performance.sql",
    "06_customer_analysis.sql",
}


def test_expected_analysis_files_exist() -> None:
    assert {path.name for path in QUERY_DIRECTORY.glob("*.sql")} == EXPECTED_FILES


def test_queries_are_nonempty_postgresql_statements() -> None:
    combined = ""
    for path in QUERY_DIRECTORY.glob("*.sql"):
        sql = path.read_text(encoding="utf-8")
        assert "select" in sql.lower()
        assert sql.rstrip().endswith(";")
        assert "nullif" in sql.lower() or path.name == "04_region_performance.sql"
        combined += sql.lower()
    for required in [
        "count(distinct transaction_id)",
        "lag(",
        "rank() over",
        "date_trunc",
        "gross_margin",
        "top_10_revenue_share",
    ]:
        assert required in combined
