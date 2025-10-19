from view import View
from model import DataModel, PortfolioModel
from datetime import datetime
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd


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
        tabs = st.tabs(["Build Portfolio", "Compare Portfolios", "Optimize Portfolio", "Information"])
        with tabs[0]:
            self.build_page()
        with tabs[1]:
            self.compare_page()
        with tabs[2]:
            self.optimize_page()
        with tabs[3]:
            self.info_page()
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
        start_date, end_date = View.compare_ui_dates("compare_")
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

    @staticmethod
    def optimize_page():
        st.header("🛠️ Optimize Portfolio")

        # --- Optimization metric selection ---
        metric = st.selectbox(
            "Optimization Objective",
            [
                "Sortino Ratio", "Sharpe Ratio", "Annualized Return",
                "Minimum Volatility", "Calmar Ratio", "Sortino + Calmar", "Beta"
            ],
            help="Select which metric to maximize/minimize for the portfolio optimization."
        )

        # --- Tick selection ---
        choice = st.radio("Tickers source", ("Saved portfolio", "Custom tickers"))
        if choice == "Saved portfolio":
            pname = st.selectbox("Choose saved portfolio", list(st.session_state.portfolios.keys()))
            tickers = list(st.session_state.portfolios[pname].keys()) if pname else []
        else:
            txt = st.text_input("Enter tickers separated by commas", value="AAPL,MSFT,GOOGL")
            tickers = [t.strip().upper() for t in txt.split(",") if t.strip()]

        if not tickers:
            st.info("Please select or enter at least one ticker.")
            return

        # --- Date range & settings ---
        start_date, end_date = View.compare_ui_dates("optimize_")
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())
        if start_dt > end_dt:
            st.warning("Start date cannot be after end date.")
            return

        n_samples = st.number_input("Number of random portfolios", min_value=100, max_value=20000, value=5000, step=100)
        rf_annual = st.number_input("Risk-free rate (annual, e.g. 0.03 = 3%)", value=0.03, step=0.005, format="%.3f")

        if st.button("Run Optimization"):
            # --- Fetch price data ---
            prices = DataModel.fetch_prices(tickers, start_dt, end_dt)
            if prices.empty:
                st.warning("No price data available for the selected tickers/date range.")
                return

            daily = prices.pct_change().dropna(how="all").dropna()
            if daily.empty:
                st.warning("Insufficient return data.")
                return

            ann_factor = 252
            rf_percent = rf_annual * 100.0
            ticks = len(tickers)
            rng = np.random.default_rng()
            W = rng.dirichlet(np.ones(ticks), size=int(n_samples))

            returns_matrix = daily.values
            port_daily = W @ returns_matrix.T
            ann_returns = ((np.prod(1 + port_daily, axis=1)) ** (ann_factor / port_daily.shape[1]) - 1) * 100
            downside = np.sqrt(np.mean(np.minimum(port_daily, 0.0) ** 2, axis=1) * ann_factor) * 100
            total_vol = np.std(port_daily, axis=1) * np.sqrt(ann_factor) * 100
            cum_returns = (1 + port_daily).cumprod(axis=1)
            max_drawdown = np.max(1 - (cum_returns / np.maximum.accumulate(cum_returns, axis=1)), axis=1) * 100

            # --- Beta calculation if needed ---
            if metric == "Beta":
                market_prices = DataModel.fetch_prices(["SPY"], start_dt, end_dt)
                market_ret = market_prices.pct_change().dropna().values.flatten()
                beta_vals = np.array([
                    np.cov(port_daily[i], market_ret, ddof=1)[0, 1] / np.var(market_ret, ddof=1)
                    for i in range(port_daily.shape[0])
                ])
                best_idx = np.argmin(np.abs(beta_vals - 1))  # closest to market
                objective = beta_vals

            # --- Compute objective for other metrics ---
            else:
                if metric == "Sortino Ratio":
                    objective = (ann_returns - rf_percent) / (downside + 1e-12)
                    best_idx = np.nanargmax(objective)
                elif metric == "Sharpe Ratio":
                    objective = (ann_returns - rf_percent) / (total_vol + 1e-12)
                    best_idx = np.nanargmax(objective)
                elif metric == "Annualized Return":
                    objective = ann_returns
                    best_idx = np.nanargmax(objective)
                elif metric == "Minimum Volatility":
                    objective = total_vol
                    best_idx = np.nanargmin(objective)
                elif metric == "Calmar Ratio":
                    objective = ann_returns / (max_drawdown + 1e-12)
                    best_idx = np.nanargmax(objective)
                elif metric == "Sortino + Calmar":
                    sortino = (ann_returns - rf_percent) / (downside + 1e-12)
                    calmar = ann_returns / (max_drawdown + 1e-12)
                    objective = sortino * calmar  # composite
                    best_idx = np.nanargmax(objective)
                else:
                    objective = ann_returns
                    best_idx = 0

            # --- Best portfolio ---
            best_w = W[best_idx]
            best_weights = {tickers[i]: float(best_w[i]) for i in range(ticks)}
            best_ann_ret = ann_returns[best_idx]
            best_downside = downside[best_idx]
            best_vol = total_vol[best_idx]
            best_dd = max_drawdown[best_idx]
            best_value = objective[best_idx]
            best_beta = beta_vals[best_idx] if metric == "Beta" else None

            # --- Scatter plot ---
            df_plot = pd.DataFrame({
                "Volatility (%)": total_vol,
                "Downside (%)": downside,
                "Drawdown (%)": max_drawdown,
                "Annual Return (%)": ann_returns,
                "Objective": objective
            })
            fig = px.scatter(
                df_plot,
                x="Volatility (%)",
                y="Annual Return (%)",
                color="Objective",
                color_continuous_scale="viridis",
                title=f"Optimization: {metric}",
                hover_data={"Volatility (%)": True, "Annual Return (%)": True, "Objective": True}
            )
            fig.add_trace(go.Scatter(
                x=[best_vol],
                y=[best_ann_ret],
                mode="markers+text",
                marker=dict(size=14, color="red", symbol="star"),
                text=["Best"],
                textposition="top center",
                showlegend=False
            ))

            st.subheader(f"Optimization results ({metric})")
            st.plotly_chart(fig, use_container_width=True)

            # --- Display best portfolio info ---
            st.write(f"**Best Portfolio (optimized for {metric})**")
            st.write(f"- Annualized Return: {best_ann_ret:.2f}%")
            st.write(f"- Volatility (annualized): {best_vol:.2f}%")
            st.write(f"- Downside Deviation: {best_downside:.2f}%")
            st.write(f"- Max Drawdown: {best_dd:.2f}%")
            if best_beta is not None:
                st.write(f"- Beta: {best_beta:.3f} (closer to 1 = market sensitivity)")
            st.write(f"- {metric}: {best_value:.3f}")

            st.table(pd.DataFrame({
                "Ticker": list(best_weights.keys()),
                "Weight (%)": [w * 100 for w in best_weights.values()]
            }).set_index("Ticker"))

            pie = px.pie(
                names=list(best_weights.keys()),
                values=[w * 100 for w in best_weights.values()],
                title="Best Portfolio Allocation (%)"
            )
            st.plotly_chart(pie, use_container_width=True)

    @staticmethod
    def info_page():
        st.header("📚 Portfolio Metrics Explained")

        st.markdown("""
        Here’s a quick guide to the key portfolio metrics and how they are calculated:
        """)

        st.subheader("1. Annualized Return (%)")
        st.markdown("The average yearly return of the portfolio, assuming compounding:")
        st.latex(r"R_\text{ann} = \left( \frac{V_\text{end}}{V_\text{start}} \right)^{\frac{252}{N}} - 1")

        st.subheader("2. Volatility (%)")
        st.markdown("Measures how much the portfolio value fluctuates (risk):")
        st.latex(r"\sigma_\text{ann} = \text{StdDev}(\text{daily returns}) \times \sqrt{252}")

        st.subheader("3. Sharpe Ratio")
        st.markdown("Risk-adjusted return using total volatility:")
        st.latex(r"S = \frac{R_\text{ann} - R_f}{\sigma_\text{ann}}")

        st.subheader("4. Sortino Ratio")
        st.markdown("Similar to Sharpe, but only considers downside volatility:")
        st.latex(r"S_\text{sortino} = \frac{R_\text{ann} - R_f}{\sigma_\text{downside}}")

        st.subheader("5. Max Drawdown (%)")
        st.markdown("Largest peak-to-trough loss:")
        st.latex(r"\text{Max Drawdown} = \max \left(1 - \frac{V_t}{\max(V_\tau)} \right)")

        st.subheader("6. Calmar Ratio")
        st.markdown("Return relative to worst drawdown:")
        st.latex(r"C = \frac{R_\text{ann}}{\text{Max Drawdown}}")

        st.subheader("7. Downside Deviation (%)")
        st.markdown("Annualized standard deviation of negative returns, used in Sortino Ratio:")
        st.latex(r"\sigma_\text{downside} = \sqrt{\text{mean}(\min(R_\text{daily}, 0)^2) \times 252}")
