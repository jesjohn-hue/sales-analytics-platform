"""Evidence-based conditions derived from calculated KPI outputs."""

from __future__ import annotations

from dataclasses import dataclass

from sales_analytics.analysis.kpis import KPIResults


@dataclass(frozen=True)
class Insight:
    condition: str
    evidence: str


def generate_insights(results: KPIResults) -> list[Insight]:
    """Identify notable calculated conditions without hard-coded conclusions."""
    insights: list[Insight] = []
    latest = results.annual.dropna(subset=["revenue_yoy_growth", "profit_yoy_growth"])
    if not latest.empty:
        row = latest.iloc[-1]
        gap = row["revenue_yoy_growth"] - row["profit_yoy_growth"]
        if gap >= 0.03:
            insights.append(
                Insight(
                    "Profit growth trails revenue growth",
                    f"Latest YoY growth gap: {gap:.1%}.",
                )
            )

    annual = results.annual.sort_values("year")
    if (
        len(annual) >= 2
        and annual["revenue_yoy_growth"].dropna().gt(0).all()
        and annual.iloc[-1]["gross_margin"] < annual.iloc[0]["gross_margin"] - 0.005
    ):
        compression = annual.iloc[0]["gross_margin"] - annual.iloc[-1]["gross_margin"]
        insights.append(
            Insight(
                "Revenue is growing while margin is compressing",
                f"Gross margin decreased {compression:.1%} from the first to the "
                "latest year.",
            )
        )

    major_products = results.products[
        results.products["revenue"] >= results.products["revenue"].median()
    ]
    overall_margin = results.overview["gross_margin"]
    if overall_margin is not None and not major_products.empty:
        weakest = major_products.sort_values("gross_margin").iloc[0]
        if weakest["gross_margin"] <= overall_margin - 0.10:
            insights.append(
                Insight(
                    "Major product has weak margin",
                    f"{weakest['product_name']} margin is "
                    f"{weakest['gross_margin']:.1%} versus "
                    f"{overall_margin:.1%} overall.",
                )
            )

    declining = results.categories[results.categories["revenue_yoy_growth"] < 0]
    if not declining.empty:
        row = declining.sort_values("revenue_yoy_growth").iloc[0]
        insights.append(
            Insight(
                "Category revenue is declining",
                f"{row['category_name']} latest YoY revenue growth is "
                f"{row['revenue_yoy_growth']:.1%}.",
            )
        )

    growing_regions = results.regions.dropna(subset=["revenue_yoy_growth"])
    if not growing_regions.empty:
        row = growing_regions.sort_values("revenue_yoy_growth", ascending=False).iloc[0]
        insights.append(
            Insight(
                "Fastest-growing region",
                f"{row['region']} latest YoY revenue growth is "
                f"{row['revenue_yoy_growth']:.1%}.",
            )
        )

    if len(results.channels) > 1:
        high = results.channels.loc[results.channels["average_order_value"].idxmax()]
        low = results.channels.loc[results.channels["average_order_value"].idxmin()]
        if (
            low["average_order_value"] > 0
            and high["average_order_value"] / low["average_order_value"] >= 1.5
        ):
            insights.append(
                Insight(
                    "Channel order values differ materially",
                    f"{high['channel_name']} AOV is "
                    f"{high['average_order_value'] / low['average_order_value']:.1f}x "
                    f"{low['channel_name']}.",
                )
            )

    share = results.concentration["top_customer_revenue_share"]
    if share is not None and share >= 0.20:
        insights.append(
            Insight(
                "Revenue is concentrated among top customers",
                f"Top {results.concentration['top_customer_count']} customers "
                f"contribute {share:.1%} of revenue.",
            )
        )
    return insights
