"""Recruiter-facing executive dashboard for the validated sales warehouse."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sales_analytics.analysis.insights import generate_insights
from sales_analytics.analysis.kpis import calculate_kpis
from sales_analytics.dashboard.data import filter_options, filter_warehouse
from sales_analytics.pipeline.extract import read_raw_sales
from sales_analytics.pipeline.transform import transform_sales

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = PROJECT_ROOT / "data/raw/sales.csv"
BLUE = "#2457D6"
GOLD = "#D69E2E"
INK = "#172033"
MUTED = "#6B7280"
GRID = "#E7EAF0"
CATEGORY_COLORS = {
    "Technology": "#2457D6",
    "Accessories": "#D69E2E",
    "Furniture": "#6C7A5B",
    "Office Supplies": "#C76D3A",
}

st.set_page_config(
    page_title="Sales Analytics Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #F7F8FB; color: #172033; }
    [data-testid="stSidebar"] { background: #111827; }
    [data-testid="stSidebar"] * { color: #F9FAFB; }
    [data-testid="stMetric"] {
        background: white; border: 1px solid #E5E7EB; border-radius: 12px;
        padding: 16px 18px; box-shadow: 0 1px 2px rgba(17, 24, 39, .04);
    }
    [data-testid="stMetricLabel"] { color: #667085; }
    [data-testid="stMetricValue"] { color: #172033; font-weight: 650; }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px; }
    h1, h2, h3 { letter-spacing: -.025em; color: #172033; }
    .eyebrow { color: #2457D6; font-size: .78rem; font-weight: 700;
        letter-spacing: .12em; text-transform: uppercase; }
    .subtitle { color: #667085; margin-top: -.6rem; margin-bottom: 1.2rem; }
    .insight { background: white; border-left: 4px solid #2457D6;
        border-radius: 8px; padding: .8rem 1rem; margin: .45rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Preparing validated sales data…")
def load_warehouse(path: str, modified_time: float):
    """Load and transform the reproducible source; mtime invalidates the cache."""
    del modified_time
    return transform_sales(read_raw_sales(path))


def money(value: float | None) -> str:
    if value is None:
        return "—"
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.2f}"


def percent(value: float | None) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.1%}"


def exact_money(value: float | None) -> str:
    return "—" if value is None else f"${value:,.2f}"


def style_chart(figure: go.Figure, *, height: int = 380) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=20, t=55, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter, Arial, sans-serif", color=INK, size=12),
        title_font=dict(size=16, color=INK),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    figure.update_xaxes(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID)
    figure.update_yaxes(gridcolor=GRID, linecolor=GRID, zerolinecolor=GRID)
    return figure


def chart(figure: go.Figure) -> None:
    st.plotly_chart(
        style_chart(figure), width="stretch", config={"displayModeBar": False}
    )


def show_insights(results) -> None:
    insights = generate_insights(results)
    if insights:
        st.markdown("### Calculated management signals")
        for insight in insights[:4]:
            st.markdown(
                f'<div class="insight"><strong>{insight.condition}</strong><br>'
                f'<span style="color:{MUTED}">{insight.evidence}</span></div>',
                unsafe_allow_html=True,
            )


if not RAW_DATA.exists():
    st.error("The generated sales file is missing. Run `make generate` first.")
    st.stop()

warehouse = load_warehouse(str(RAW_DATA), RAW_DATA.stat().st_mtime)
options = filter_options(warehouse)

with st.sidebar:
    st.markdown("## Sales Analytics")
    st.caption("Validated synthetic portfolio dataset")
    st.markdown("---")
    selected_years = st.multiselect("Year", options["years"], default=options["years"])
    selected_regions = st.multiselect(
        "Region", options["regions"], default=options["regions"]
    )
    selected_categories = st.multiselect(
        "Product category", options["categories"], default=options["categories"]
    )
    selected_channels = st.multiselect(
        "Sales channel", options["channels"], default=options["channels"]
    )
    st.markdown("---")
    st.caption("Sales-line grain • USD • Jan 2023–Dec 2025")

filtered = filter_warehouse(
    warehouse,
    years=selected_years,
    regions=selected_regions,
    categories=selected_categories,
    channels=selected_channels,
)
if filtered.fact_sales.empty:
    st.warning("No sales match the selected filters. Expand at least one filter.")
    st.stop()

results = calculate_kpis(filtered)
overview = results.overview

st.markdown(
    '<div class="eyebrow">Business Intelligence Portfolio</div>', unsafe_allow_html=True
)
st.title("Executive Sales Performance")
st.markdown(
    '<div class="subtitle">Interactive management view built from validated Python '
    "KPI definitions and a PostgreSQL dimensional model.</div>",
    unsafe_allow_html=True,
)

tabs = st.tabs(
    [
        "Executive Overview",
        "Product & Profitability",
        "Regional & Channel",
        "Customer Analysis",
    ]
)

with tabs[0]:
    cards = st.columns(4)
    cards[0].metric("Total Revenue", money(overview["total_revenue"]))
    cards[1].metric("Total Profit", money(overview["total_profit"]))
    cards[2].metric("Gross Margin", percent(overview["gross_margin"]))
    cards[3].metric("Transactions", f"{overview['transactions']:,}")
    cards = st.columns(3)
    cards[0].metric("Average Order Value", exact_money(overview["average_order_value"]))
    cards[1].metric("Unique Customers", f"{overview['unique_customers']:,}")
    cards[2].metric("Repeat Customer Rate", percent(overview["repeat_customer_rate"]))

    monthly_long = results.monthly.melt(
        id_vars="month",
        value_vars=["revenue", "profit"],
        var_name="Metric",
        value_name="USD",
    )
    monthly_figure = px.line(
        monthly_long,
        x="month",
        y="USD",
        color="Metric",
        markers=True,
        title="Monthly Revenue and Profit",
        color_discrete_map={"revenue": BLUE, "profit": GOLD},
    )
    monthly_figure.update_yaxes(tickprefix="$", tickformat="~s")
    chart(monthly_figure)

    left, right = st.columns(2)
    with left:
        annual_long = results.annual.melt(
            id_vars="year",
            value_vars=["revenue", "profit"],
            var_name="Metric",
            value_name="USD",
        )
        annual_figure = px.bar(
            annual_long,
            x="year",
            y="USD",
            color="Metric",
            barmode="group",
            title="Annual Revenue and Profit",
            color_discrete_map={"revenue": BLUE, "profit": GOLD},
        )
        annual_figure.update_yaxes(tickprefix="$", tickformat="~s")
        chart(annual_figure)
    with right:
        region_figure = px.bar(
            results.regions.sort_values("revenue"),
            x="revenue",
            y="region",
            orientation="h",
            title="Revenue by Region",
            color_discrete_sequence=[BLUE],
        )
        region_figure.update_xaxes(tickprefix="$", tickformat="~s")
        chart(region_figure)

    channel_figure = px.bar(
        results.channels.sort_values("revenue"),
        x="channel_name",
        y="revenue",
        title="Revenue by Sales Channel",
        color_discrete_sequence=[BLUE],
    )
    channel_figure.update_yaxes(tickprefix="$", tickformat="~s")
    chart(channel_figure)
    show_insights(results)

with tabs[1]:
    scatter = px.scatter(
        results.products,
        x="revenue",
        y="gross_margin",
        size="profit",
        color="category_name",
        hover_name="product_name",
        hover_data={"revenue": ":$,.0f", "profit": ":$,.0f", "gross_margin": ":.1%"},
        title="Product Revenue versus Gross Margin",
        color_discrete_map=CATEGORY_COLORS,
        size_max=38,
    )
    scatter.add_hline(
        y=overview["gross_margin"],
        line_dash="dash",
        line_color=INK,
        annotation_text="Portfolio margin",
        annotation_position="top left",
    )
    scatter.update_xaxes(tickprefix="$", tickformat="~s")
    scatter.update_yaxes(tickformat=".0%")
    chart(scatter)

    left, right = st.columns(2)
    with left:
        top_revenue = results.products.nsmallest(10, "revenue_rank").sort_values(
            "revenue"
        )
        figure = px.bar(
            top_revenue,
            x="revenue",
            y="product_name",
            orientation="h",
            title="Top Products by Revenue",
            color_discrete_sequence=[BLUE],
        )
        figure.update_xaxes(tickprefix="$", tickformat="~s")
        chart(figure)
    with right:
        top_profit = results.products.nsmallest(10, "profit_rank").sort_values("profit")
        figure = px.bar(
            top_profit,
            x="profit",
            y="product_name",
            orientation="h",
            title="Top Products by Profit",
            color_discrete_sequence=[GOLD],
        )
        figure.update_xaxes(tickprefix="$", tickformat="~s")
        chart(figure)

    category_long = results.categories.melt(
        id_vars="category_name",
        value_vars=["revenue", "profit"],
        var_name="Metric",
        value_name="USD",
    )
    category_figure = px.bar(
        category_long,
        x="category_name",
        y="USD",
        color="Metric",
        barmode="group",
        title="Category Revenue and Profit",
        color_discrete_map={"revenue": BLUE, "profit": GOLD},
    )
    category_figure.update_yaxes(tickprefix="$", tickformat="~s")
    chart(category_figure)

    category_trend = px.line(
        results.category_annual,
        x="year",
        y="revenue",
        color="category_name",
        markers=True,
        title="Category Revenue by Year",
        color_discrete_map=CATEGORY_COLORS,
    )
    category_trend.update_yaxes(tickprefix="$", tickformat="~s")
    chart(category_trend)
    st.dataframe(
        results.products[
            ["product_name", "category_name", "revenue", "profit", "gross_margin"]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
            "gross_margin": st.column_config.NumberColumn(
                "Gross Margin", format="percent"
            ),
        },
    )

with tabs[2]:
    left, right = st.columns(2)
    with left:
        region_long = results.regions.melt(
            id_vars="region",
            value_vars=["revenue", "profit"],
            var_name="Metric",
            value_name="USD",
        )
        figure = px.bar(
            region_long,
            x="region",
            y="USD",
            color="Metric",
            barmode="group",
            title="Regional Revenue and Profit",
            color_discrete_map={"revenue": BLUE, "profit": GOLD},
        )
        figure.update_yaxes(tickprefix="$", tickformat="~s")
        chart(figure)
    with right:
        growth = results.regions.sort_values("revenue_yoy_growth")
        figure = px.bar(
            growth,
            x="revenue_yoy_growth",
            y="region",
            orientation="h",
            title="Latest Regional YoY Revenue Growth",
            color_discrete_sequence=[BLUE],
        )
        figure.update_xaxes(tickformat=".0%")
        chart(figure)

    margin = px.bar(
        results.regions.sort_values("gross_margin"),
        x="gross_margin",
        y="region",
        orientation="h",
        title="Regional Gross Margin",
        color_discrete_sequence=[GOLD],
    )
    margin.update_xaxes(tickformat=".0%")
    chart(margin)

    channel_long = results.channels.melt(
        id_vars="channel_name",
        value_vars=["revenue", "profit"],
        var_name="Metric",
        value_name="USD",
    )
    figure = px.bar(
        channel_long,
        x="channel_name",
        y="USD",
        color="Metric",
        barmode="group",
        title="Channel Revenue and Profit",
        color_discrete_map={"revenue": BLUE, "profit": GOLD},
    )
    figure.update_yaxes(tickprefix="$", tickformat="~s")
    chart(figure)
    left, right = st.columns(2)
    with left:
        figure = px.bar(
            results.channels.sort_values("gross_margin"),
            x="channel_name",
            y="gross_margin",
            title="Channel Gross Margin",
            color_discrete_sequence=[GOLD],
        )
        figure.update_yaxes(tickformat=".0%")
        chart(figure)
    with right:
        figure = px.bar(
            results.channels.sort_values("average_order_value"),
            x="channel_name",
            y="average_order_value",
            title="Channel Average Order Value",
            color_discrete_sequence=[BLUE],
        )
        figure.update_yaxes(tickprefix="$", tickformat=",.0f")
        chart(figure)

with tabs[3]:
    cards = st.columns(4)
    cards[0].metric("Unique Customers", f"{overview['unique_customers']:,}")
    cards[1].metric("Repeat Customer Rate", percent(overview["repeat_customer_rate"]))
    cards[2].metric(
        "Revenue per Customer", money(overview["average_revenue_per_customer"])
    )
    cards[3].metric(
        "Top 10 Revenue Share",
        percent(results.concentration["top_customer_revenue_share"]),
    )
    st.caption("Customer lifetime revenue is limited to the selected dataset period.")

    top_customers = results.customers.head(15).sort_values("lifetime_revenue")
    figure = px.bar(
        top_customers,
        x="lifetime_revenue",
        y="customer_id",
        orientation="h",
        title="Top Customers by Dataset-Period Revenue",
        color_discrete_sequence=[BLUE],
    )
    figure.update_xaxes(tickprefix="$", tickformat="~s")
    chart(figure)

    left, right = st.columns(2)
    with left:
        distribution = px.histogram(
            results.customers,
            x="lifetime_revenue",
            nbins=35,
            title="Customer Revenue Distribution",
            color_discrete_sequence=[BLUE],
        )
        distribution.update_xaxes(tickprefix="$", tickformat="~s")
        distribution.update_yaxes(title="Customers")
        chart(distribution)
    with right:
        comparison = (
            results.customers.assign(
                customer_type=results.customers["transactions"]
                .ge(2)
                .map({True: "Repeat", False: "One-time"})
            )
            .groupby("customer_type", as_index=False)
            .agg(
                customers=("customer_id", "nunique"),
                revenue=("lifetime_revenue", "sum"),
            )
        )
        figure = px.bar(
            comparison,
            x="customer_type",
            y="revenue",
            title="Revenue from Repeat versus One-Time Customers",
            color_discrete_sequence=[BLUE],
        )
        figure.update_yaxes(tickprefix="$", tickformat="~s")
        chart(figure)
        st.dataframe(comparison, hide_index=True, width="stretch")

st.caption(
    "Source: reproducible synthetic sales data transformed at sales-line grain. "
    "Definitions: docs/kpi_definitions.md. Descriptive analysis only; no causal claims."
)
