from view import View
from model import DataModel, PortfolioModel
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime


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
        page = st.sidebar.selectbox("Choose page", ["Build Portfolio", "Compare Portfolios"])
        if page == "Build Portfolio":
            self.build_page()
        else:
            self.compare_page()
        View.footer()

    @staticmethod
    def build_page():
        name, portfolio = View.build_portfolio_ui()
        if st.button("Save Portfolio"):
            if not name or not portfolio:
                st.warning("Please provide a portfolio name and at least one asset.")
            else:
                st.session_state.portfolios[name] = portfolio
                st.success(f"Saved portfolio '{name}'.")
        View.show_saved_portfolios(st.session_state.portfolios)

    @staticmethod
    def compare_page():
        st.header("📈 Compare Portfolios")
        start_date, end_date = View.compare_ui_default_dates()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        if start_dt > end_dt:
            st.warning("Start date cannot be after end date.")
            return

        st.info(f"Backtesting from **{start_dt.strftime('%Y-%m-%d')}** to **{end_dt.strftime('%Y-%m-%d')}**.")

        selected = st.multiselect("Select portfolios", list(st.session_state.portfolios.keys()))
        if st.button("Run Backtest") and selected:
            tickers = sorted({t for p in selected for t in st.session_state.portfolios[p]})
            with st.spinner("Fetching price data..."):
                prices = DataModel.fetch_prices(tickers, start_dt, end_dt)

            if prices.empty:
                st.warning("No price data available.")
                return

            metrics_list, pie_figs, growth_fig = [], {}, go.Figure()
            raw_scores, temp = [], []

            for pname in selected:
                weights = st.session_state.portfolios[pname]
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
                raw = ann_ret * (risk["sharpe_ratio"] + risk["sortino_ratio"]) / 2
                raw_scores.append(raw)

                temp.append({
                    "Portfolio": pname,
                    "Total Return (%)": total_ret,
                    "Annualized Return (%)": ann_ret,
                    "Sharpe Ratio": risk["sharpe_ratio"],
                    "Sortino Ratio": risk["sortino_ratio"],
                    "Max Drawdown": risk["max_drawdown"],
                    "Raw Score": raw,
                    "ValueSeries": val
                })

            # Normalize performance score 0-100
            if temp:
                min_s, max_s = min(raw_scores), max(raw_scores)
                for e in temp:
                    e["Performance Score"] = (
                        (e["Raw Score"] - min_s) / (max_s - min_s) * 100
                        if max_s > min_s else 100
                    )
                    metrics_list.append({
                        "Portfolio": e["Portfolio"],
                        "Total Return (%)": e["Total Return (%)"],
                        "Annualized Return (%)": e["Annualized Return (%)"],
                        "Sharpe Ratio": e["Sharpe Ratio"],
                        "Sortino Ratio": e["Sortino Ratio"],
                        "Max Drawdown": e["Max Drawdown"],
                        "Performance Score": e["Performance Score"]
                    })
                    w = st.session_state.portfolios[e["Portfolio"]]
                    labels = [t for t in w if t in prices.columns]
                    values = [w[t] for t in labels]
                    pie = px.pie(names=labels, values=[v * 100 for v in values],
                                 title=f"{e['Portfolio']} Allocation (%)")
                    pie_figs[e["Portfolio"]] = pie
                    growth_fig.add_trace(go.Scatter(
                        x=e["ValueSeries"].index, y=e["ValueSeries"], name=e["Portfolio"], mode="lines"))

            View.show_metrics_table(metrics_list)
            View.show_pie_charts(pie_figs)
            View.show_growth_chart(growth_fig)
