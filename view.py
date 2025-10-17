from typing import Dict, List
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

APP_TITLE = "Automatic Investment"


class View:
    """Handles all UI rendering for the Streamlit app."""

    @staticmethod
    def set_page():
        """Set Streamlit page configuration."""
        st.set_page_config(page_title=APP_TITLE, layout="wide")

    @staticmethod
    def header():
        """Display main title."""
        st.title(APP_TITLE)

    @staticmethod
    def build_portfolio_ui():
        """UI for building a new investment portfolio."""
        st.header("🛠 Build Your Portfolio")
        name = st.text_input("Portfolio Name", "My Portfolio")
        n = st.number_input("Number of assets", min_value=1, max_value=20, value=3, step=1)

        cols = st.columns(2)
        portfolio = {}
        for i in range(n):
            with cols[0]:
                ticker = st.text_input(f"Asset {i + 1} Ticker", key=f"ticker_{i}").strip().upper()
            with cols[1]:
                w = st.number_input(f"Weight (%)", min_value=0.1, max_value=100.0, value=100.0 / n, step=0.1, key=f"weight_{i}")
            if ticker:
                portfolio[ticker] = w / 100.0
        return name, portfolio

    @staticmethod
    def show_saved_portfolios(portfolios: Dict[str, Dict[str, float]]):
        """Display all saved portfolios."""
        st.subheader("Saved Portfolios")
        if not portfolios:
            st.info("No portfolios saved yet.")
            return
        for name, data in portfolios.items():
            st.write(f"**{name}**: " + ", ".join([f"{t} ({w * 100:.1f}%)" for t, w in data.items()]))

    @staticmethod
    def compare_ui_default_dates():
        """Default date picker for comparison."""
        today = datetime.today()
        default_end = today
        default_start = today - timedelta(days=365)

        start_date = st.date_input("Start Date", value=default_start.date(), max_value=today.date())
        end_date = st.date_input("End Date", value=default_end.date(), max_value=today.date())
        return start_date, end_date

    @staticmethod
    def show_metrics_table(metrics_list: List[dict]):
        """Display portfolio performance metrics in a formatted table."""
        if not metrics_list:
            st.info("No portfolio metrics to display.")
            return

        st.subheader("📊 Portfolio Metrics Comparison")
        df = pd.DataFrame(metrics_list).set_index("Portfolio")

        st.dataframe(
            df.style.format({
                "Total Return (%)": "{:.2f}",
                "Annualized Return (%)": "{:.2f}",
                "Sharpe Ratio": "{:.2f}",
                "Sortino Ratio": "{:.2f}",
                "Max Drawdown": "{:.2%}",
                "Performance Score": "{:.2f}"
            }),
            use_container_width=True
        )

    @staticmethod
    def show_pie_charts(pie_figs: Dict[str, go.Figure]):
        """Display pie charts for each portfolio’s asset allocation."""
        if not pie_figs:
            return

        st.subheader("🥧 Asset Allocation")
        cols = st.columns(len(pie_figs))
        for i, (name, fig) in enumerate(pie_figs.items()):
            with cols[i]:
                st.plotly_chart(fig, config={"responsive": True}, use_container_width=True)

    @staticmethod
    def show_growth_chart(fig: go.Figure):
        """Display a portfolio value growth line chart."""
        if not fig.data:
            st.info("No valid portfolio value data to plot.")
            return

        st.subheader("📈 Portfolio Value Over Time")
        fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig, config={"responsive": True}, use_container_width=True)

    @staticmethod
    def footer():
        """Display app footer."""
        st.markdown("---")
        st.markdown(
            """
            <div style="text-align:center; color:gray;">
            Made with ❤️ by <b>Luis Ng</b> |
            <a href="https://github.com/CodingLuisNg" target="_blank">GitHub</a>
            </div>
            """,
            unsafe_allow_html=True
        )
