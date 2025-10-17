"""
Automatic Investment - Streamlit App (Refined, yfinance-only, MVC style)

Architecture:
- Model: data fetching & portfolio analytics
- View: Streamlit UI components
- Controller: connects View ↔ Model logic
"""

from typing import Dict, List, Tuple
import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

# -----------------------------
# Configuration
# -----------------------------
APP_TITLE = "Automatic Investment"
CACHE_TTL = 24 * 3600  # 1 day cache


# -----------------------------
# Model Layer
# -----------------------------
class DataModel:
    """Fetches and processes price data directly from yfinance."""

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL)
    def fetch_prices(tickers: List[str], start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch adjusted close prices for tickers between start and end using yfinance."""
        if not tickers:
            return pd.DataFrame()

        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
        tickers = [t.upper() for t in tickers]

        all_series = {}
        batch_size = 5  # prevent rate-limit issues

        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            try:
                raw = yf.download(
                    tickers=batch,
                    start=start.strftime("%Y-%m-%d"),
                    end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    progress=False,
                    group_by="ticker",
                    auto_adjust=True
                )
            except Exception as e:
                print(f"[DataModel] yfinance download failed for {batch}: {e}")
                continue

            # Handle both single- and multi-ticker downloads
            if isinstance(raw.columns, pd.MultiIndex):
                for t in batch:
                    try:
                        # Ensure the ticker exists in raw and is a DataFrame
                        ticker_data = raw[t] if t in raw else None
                        if ticker_data is None or ticker_data.empty:
                            continue

                        if "Close" not in ticker_data.columns:
                            continue

                        close = ticker_data["Close"].dropna()
                        close = close.loc[(close.index >= start) & (close.index <= end)]
                        if not close.empty:
                            close.name = t
                            all_series[t] = close

                    except Exception as e:
                        print(f"[DataModel] Failed to parse {t}: {e}")
            else:
                if "Close" in raw.columns:
                    t = batch[0]
                    close = raw["Close"].dropna()
                    close = close.loc[(close.index >= start) & (close.index <= end)]
                    if not close.empty:
                        close.name = t
                        all_series[t] = close

        if not all_series:
            return pd.DataFrame()

        df = pd.concat(all_series.values(), axis=1)
        df = df.sort_index().loc[~df.index.duplicated(keep="first")]
        df.dropna(how="all", inplace=True)
        return df


class PortfolioModel:
    """Performs portfolio valuation, returns, and risk metric calculations."""

    @staticmethod
    def portfolio_value_from_prices(prices: pd.DataFrame, weights: Dict[str, float], initial_investment: float = 10_000.0) -> Tuple[pd.Series, pd.Series]:
        if prices.empty or not weights:
            return pd.Series(dtype=float), pd.Series(dtype=float)

        weights_available = {t.upper(): w for t, w in weights.items() if t.upper() in prices.columns}
        total = sum(weights_available.values())
        if total <= 0:
            return pd.Series(dtype=float), pd.Series(dtype=float)
        normalized = {t: w / total for t, w in weights_available.items()}

        first_prices = prices.iloc[0]
        initial_shares = {
            t: (initial_investment * w) / first_prices[t]
            for t, w in normalized.items()
            if t in first_prices and first_prices[t] > 0
        }
        if not initial_shares:
            return pd.Series(dtype=float), pd.Series(dtype=float)

        value = pd.Series(0.0, index=prices.index)
        for t, shares in initial_shares.items():
            value += prices[t] * shares

        returns = value.pct_change().dropna()

        return value, returns

    @staticmethod
    def risk_metrics(daily_returns: pd.Series, risk_free_rate_annual: float = 0.03) -> Dict[str, float]:
        if daily_returns.empty:
            return {"sharpe_ratio": 0.0, "sortino_ratio": 0.0, "volatility_annual": 0.0, "max_drawdown": 0.0}

        ann_factor = 252
        vol_ann = daily_returns.std() * math.sqrt(ann_factor)
        rf_daily = risk_free_rate_annual / ann_factor
        excess = daily_returns.mean() - rf_daily
        sharpe = (excess / daily_returns.std()) * math.sqrt(ann_factor) if daily_returns.std() > 0 else 0.0

        downside = daily_returns[daily_returns < 0]
        downside_dev = downside.std() * math.sqrt(ann_factor) if len(downside) > 0 else 0.0
        sortino = (excess / downside_dev) * math.sqrt(ann_factor) if downside_dev > 0 else 0.0

        cum = (1 + daily_returns).cumprod()
        running_max = cum.cummax()
        drawdown = (cum / running_max) - 1
        max_dd = drawdown.min() if not drawdown.empty else 0.0

        return {
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "volatility_annual": float(vol_ann),
            "max_drawdown": float(max_dd)
        }

    @staticmethod
    def annualized_return(total_return_pct: float, days: int) -> float:
        if days <= 0:
            return 0.0
        total = 1 + total_return_pct / 100.0
        return (total ** (365.0 / days) - 1) * 100.0


# -----------------------------
# View Layer
# -----------------------------
class View:
    @staticmethod
    def set_page():
        st.set_page_config(page_title=APP_TITLE, layout="wide")

    @staticmethod
    def header():
        st.title(APP_TITLE)

    @staticmethod
    def build_portfolio_ui():
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
        st.subheader("Saved Portfolios")
        if not portfolios:
            st.info("No portfolios saved yet.")
            return
        for name, data in portfolios.items():
            st.write(f"**{name}**: " + ", ".join([f"{t} ({w*100:.1f}%)" for t, w in data.items()]))

    @staticmethod
    def compare_ui_default_dates():
        today = datetime.today()
        default_end = today
        default_start = today - timedelta(days=365)

        start_date = st.date_input("Start Date", value=default_start.date(), max_value=today.date())
        end_date = st.date_input("End Date", value=default_end.date(), max_value=today.date())
        return start_date, end_date

    @staticmethod
    def show_metrics_table(metrics_list: List[dict]):
        if not metrics_list:
            st.info("No portfolio metrics to display.")
            return
        st.subheader("📊 Portfolio Metrics Comparison")
        df = pd.DataFrame(metrics_list).set_index("Portfolio")
        st.dataframe(df.style.format({
            "Total Return (%)": "{:.2f}",
            "Annualized Return (%)": "{:.2f}",
            "Sharpe Ratio": "{:.2f}",
            "Sortino Ratio": "{:.2f}",
            "Max Drawdown": "{:.2%}",
            "Performance Score": "{:.2f}"
        }), use_container_width=True)

    @staticmethod
    def show_pie_charts(pie_figs: Dict[str, go.Figure]):
        if not pie_figs:
            return
        st.subheader("🥧 Asset Allocation")
        cols = st.columns(len(pie_figs))
        for i, (name, fig) in enumerate(pie_figs.items()):
            with cols[i]:
                st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def show_growth_chart(fig: go.Figure):
        if not fig.data:
            st.info("No valid portfolio value data to plot.")
            return
        st.subheader("📈 Portfolio Value Over Time")
        fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Value")
        st.plotly_chart(fig, use_container_width=True)

    @staticmethod
    def footer():
        st.markdown("---")
        st.markdown(
            """
            <div style="text-align:center; color:gray;">
            Made with ❤️ by **Luis Ng** |
            <a href="https://github.com/CodingLuisNg" target="_blank">GitHub</a>
            </div>
            """, unsafe_allow_html=True
        )


# -----------------------------
# Controller Layer
# -----------------------------
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


# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    controller = Controller()
    controller.run()
