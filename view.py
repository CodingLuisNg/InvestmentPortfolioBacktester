from typing import Dict, List
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

APP_TITLE = "Student Portfolio Playground"


class View:
    """Handles all UI rendering for the Streamlit app."""

    @staticmethod
    def set_page():
        st.set_page_config(page_title=APP_TITLE, layout="wide")

    @staticmethod
    def header():
        st.title(APP_TITLE)

    @staticmethod
    def build_portfolio_ui():
        """UI for building a new investment portfolio with remove option."""
        # Initialize session state
        if "tickers" not in st.session_state:
            st.session_state.tickers = []
        if "new_ticker" not in st.session_state:
            st.session_state.new_ticker = ""

        st.header("🛠 Build Your Portfolio")
        name = st.text_input("Portfolio Name", "My Portfolio")

        # Input new ticker
        new_ticker = st.text_input(
            "Enter a ticker and press Enter to add",
            value=st.session_state.new_ticker,
            key="new_ticker_input"
        )

        # Add ticker if valid
        if new_ticker:
            ticker = new_ticker.strip().upper()
            if ticker and ticker not in st.session_state.tickers:
                st.session_state.tickers.append(ticker)
                st.session_state.new_ticker = ""
                st.rerun()

        portfolio = {}
        # Use a copy to avoid modifying during iteration
        tickers_copy = st.session_state.tickers.copy()

        # Display ticker rows
        for i, ticker in enumerate(tickers_copy):
            col0, col1, col2 = st.columns([0.1, 0.6, 0.3])
            # Use ticker as part of key for stability
            remove_key = f"remove_{ticker}_{i}"

            # Handle remove button click
            if col0.button("❌", key=remove_key):
                st.session_state.tickers.remove(ticker)
                st.rerun()  # Immediate rerun to update UI

            # Ticker input
            t_new = col1.text_input(f"Ticker {i + 1}", value=ticker, key=f"ticker_{ticker}_{i}")
            # Weight input
            w = col2.number_input(
                "Weight (%)",
                min_value=0.1,
                max_value=100.0,
                value=100.0 / max(len(tickers_copy), 1),
                step=0.1,
                key=f"weight_{ticker}_{i}"
            )
            portfolio[t_new] = w / 100.0
            # Update ticker if edited
            if t_new != ticker and t_new:
                st.session_state.tickers[st.session_state.tickers.index(ticker)] = t_new

        # Validate total weight before saving
        total_weight = sum(portfolio.values())
        if total_weight < 0.99 or total_weight > 1.01:
            st.warning(f"Total portfolio weight is {total_weight * 100:.1f}%. Adjust weights to sum to 100%.")
            submitted = False
        else:
            submitted = st.button("Save Portfolio")

        return name, portfolio, submitted

    @staticmethod
    def show_saved_portfolios(portfolios: Dict[str, Dict[str, float]]):
        st.subheader("Saved Portfolios")
        if not portfolios:
            st.info("No portfolios saved yet.")
            return

        # Use a copy to avoid modifying during iteration
        portfolios_copy = portfolios.copy()
        for name, data in portfolios_copy.items():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{name}**: " + ", ".join([f"{t} ({w * 100:.1f}%)" for t, w in data.items()]))
            with col2:
                delete_key = f"delete_portfolio_{name}"
                if st.button("❌ Delete", key=delete_key):
                    st.session_state.portfolios.pop(name, None)
                    st.rerun()  # Immediate rerun to update UI

    @staticmethod
    def compare_ui_dates():
        """Date picker for comparison; no lower limit."""
        today = datetime.today()
        default_start = today - timedelta(days=365)
        start_date = st.date_input("Start Date", value=default_start.date())
        end_date = st.date_input("End Date", value=today.date())
        return start_date, end_date

    @staticmethod
    def show_metrics_table(metrics_list: List[dict]):
        """Display portfolio performance metrics including avg volatility."""
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
                "Average Volatility (%)": "{:.2f}"
            }),
            width='stretch'
        )

    @staticmethod
    def show_pie_charts(pie_figs: Dict[str, go.Figure]):
        if not pie_figs:
            return
        st.subheader("🥧 Asset Allocation")
        cols = st.columns(len(pie_figs))
        for i, (name, fig) in enumerate(pie_figs.items()):
            with cols[i]:
                st.plotly_chart(fig)

    @staticmethod
    def show_growth_chart(fig: go.Figure):
        if not fig.data:
            st.info("No valid portfolio value data to plot.")
            return
        st.subheader("📈 Portfolio Value Over Time")
        fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig)

    @staticmethod
    def show_risk_return(risk_list: List[float], return_list: List[float], names: List[str]):
        """Show risk vs return scatter plot."""
        if not risk_list or not return_list:
            return
        st.subheader("⚖️ Risk vs Reward")
        fig = px.scatter(
            x=risk_list, y=return_list, text=names,
            labels={"x": "Annualized Volatility (%)", "y": "Annualized Return (%)"},
        )
        fig.update_traces(textposition="top center", marker=dict(size=15, color='royalblue'))
        st.plotly_chart(fig)

    @staticmethod
    def show_correlation_heatmaps(all_prices: dict):
        """
        Show correlation heatmaps for each portfolio side by side.

        all_prices: dict
            Dictionary where keys are portfolio names, values are DataFrames of prices for that portfolio.
        """
        if not all_prices:
            return

        st.subheader("🔗Correlation Heatmap")
        n = len(all_prices)
        cols = st.columns(n)

        for i, (pname, prices) in enumerate(all_prices.items()):
            if prices.empty:
                continue
            corr = prices.pct_change().corr()
            fig = px.imshow(
                corr,
                text_auto=True,
                color_continuous_scale="RdBu_r",
                title=pname
            )
            with cols[i]:
                st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def footer():
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
