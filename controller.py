from view import View
from model import DataModel, PortfolioModel
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np


class Controller:
    def __init__(self):
        View.set_page()
        View.header()
        if "portfolios" not in st.session_state:
            st.session_state.portfolios = {
                "Balanced 60/40": {"SPY": 0.6, "AGG": 0.4},
                "S&P500": {"VOO": 1.0}
            }

    def run(self):
        tabs = st.tabs(["Build Portfolio", "Compare Portfolios"])
        with tabs[0]:
            self.build_page()
        with tabs[1]:
            self.compare_page()
        View.footer()

    @staticmethod
    def build_page():
        name, portfolio, submitted = View.build_portfolio_ui()
        if submitted:
            if not name or not portfolio:
                st.warning("Please provide a portfolio name and at least one asset.")
            else:
                st.session_state.portfolios[name] = portfolio
                st.success(f"Saved portfolio '{name}'.")
        View.show_saved_portfolios(st.session_state.portfolios)

    @staticmethod
    def compare_page():
        st.header("📈 Compare Portfolios")
        start_date, end_date = View.compare_ui_dates()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        if start_dt > end_dt:
            st.warning("Start date cannot be after end date.")
            return

        selected = st.multiselect("Select portfolios", list(st.session_state.portfolios.keys()))
        if st.button("Run Backtest") and selected:
            tickers = sorted({t for p in selected for t in st.session_state.portfolios[p]})
            prices = DataModel.fetch_prices(tickers, start_dt, end_dt)
            if prices.empty:
                st.warning("No price data available.")
                return

            metrics_list, pie_figs, growth_fig = [], {}, go.Figure()
            risk_list, return_list, names = [], [], []

            for PNAME in selected:
                weights = st.session_state.portfolios[PNAME]
                available = [t for t in weights if t in prices.columns]
                if not available:
                    continue
                sub_prices = prices[available].dropna(how="all")
                val, ret = PortfolioModel.portfolio_value_from_prices(sub_prices, weights)
                if val.empty:
                    continue

                total_ret = (val.iloc[-1] / val.iloc[0] - 1) * 100
                days = (val.index[-1] - val.index[0]).days
                ann_ret = PortfolioModel.annualized_return(total_ret, days)
                risk = PortfolioModel.risk_metrics(ret)
                avg_vol = ret.std() * np.sqrt(252) * 100  # annualized volatility

                metrics_list.append({
                    "Portfolio": PNAME,
                    "Total Return (%)": total_ret,
                    "Annualized Return (%)": ann_ret,
                    "Sharpe Ratio": risk["sharpe_ratio"],
                    "Sortino Ratio": risk["sortino_ratio"],
                    "Max Drawdown": risk["max_drawdown"],
                    "Average Volatility (%)": avg_vol
                })

                # Prepare risk-return plot
                risk_list.append(avg_vol)
                return_list.append(ann_ret)
                names.append(PNAME)

                # Growth chart
                growth_fig.add_trace(go.Scatter(x=val.index, y=val, name=PNAME, mode="lines"))

                # Pie chart
                labels = [t for t in weights if t in prices.columns]
                values = [weights[t]*100 for t in labels]
                pie_figs[PNAME] = px.pie(names=labels, values=values, title=f"{PNAME} Allocation (%)")

            portfolio_prices = {}
            for pname in selected:
                weights = st.session_state.portfolios[pname]
                available = [t for t in weights if t in prices.columns]
                if available:
                    portfolio_prices[pname] = prices[available].dropna(how="all")

            View.show_metrics_table(metrics_list)
            View.show_growth_chart(growth_fig)
            View.show_pie_charts(pie_figs)
            View.show_risk_return(risk_list, return_list, names)
            View.show_correlation_heatmaps(portfolio_prices)
