"""Smoke-test the executive dashboard against the deterministic dataset."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_renders_canonical_headline_metrics_without_errors() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "dashboard/app.py", default_timeout=30).run()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Executive Overview",
        "Product & Profitability",
        "Regional & Channel",
        "Customer Analysis",
    ]
    metrics = {metric.label: metric.value for metric in app.metric[:7]}
    assert metrics == {
        "Total Revenue": "$33.41M",
        "Total Profit": "$8.74M",
        "Gross Margin": "26.2%",
        "Transactions": "33,017",
        "Average Order Value": "$1,011.88",
        "Unique Customers": "3,777",
        "Repeat Customer Rate": "75.9%",
    }
