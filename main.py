import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta


# -----------------------------
# Helper functions
# -----------------------------
DATA_FOLDER = "dataset"  # path to your TXT files

@st.cache_data(ttl=24 * 3600)  # Cache for 24 hours
def batch_download(tickers, start, end):
    """
    Load historical Close prices from local TXT files.
    Returns a DataFrame with tickers as columns and dates as index.
    """
    all_data = {}
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)

    for ticker in tickers:
        # Use lowercase file names with .txt
        file_path = os.path.join(DATA_FOLDER, f"{ticker.lower()}.txt")
        if not os.path.exists(file_path):
            print(f"File not found for ticker {ticker}")
            continue

        df = pd.read_csv(file_path, parse_dates=['Date'])
        df = df.set_index('Date')
        df = df.loc[(df.index >= start) & (df.index <= end)]

        if 'Close' not in df.columns:
            print(f"'Close' column missing in {ticker}.txt")
            continue

        all_data[ticker.upper()] = df['Close']  # Keep ticker uppercase in DataFrame

    if not all_data:
        return pd.DataFrame()  # No data found
    else:
        df_all = pd.DataFrame(all_data).sort_index()
        df_all.dropna(how='all', inplace=True)
        return df_all

def calculate_portfolio_value(df, weights, initial_investment=10000):
    # Normalize weights
    weights_sum = sum(weights.values())
    normalized_weights = {ticker: w / weights_sum for ticker, w in weights.items() if ticker in df.columns}
    if not normalized_weights:
        return pd.Series(), pd.Series()

    # Calculate initial shares
    initial_shares = {t: (initial_investment * w) / df[t].iloc[0] for t, w in normalized_weights.items() if
                      df[t].iloc[0] > 0}

    # Portfolio value over time
    portfolio_value = pd.Series(0.0, index=df.index)
    for t, shares in initial_shares.items():
        portfolio_value += df[t] * shares

    # Daily returns
    portfolio_returns = portfolio_value.pct_change().dropna()

    return portfolio_value, portfolio_returns


def calculate_risk_metrics(returns_series):
    metrics = {}
    if returns_series.empty:
        return {
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "max_drawdown": 0
        }
    annual_factor = 252
    # Volatility
    vol = returns_series.std() * np.sqrt(annual_factor)
    # Sharpe Ratio
    risk_free = 0.03 / 252
    excess_return = returns_series.mean() - risk_free
    sharpe = (excess_return / returns_series.std()) * np.sqrt(annual_factor) if returns_series.std() > 0 else 0
    # Sortino
    downside = returns_series[returns_series < 0]
    downside_dev = downside.std() * np.sqrt(annual_factor) if len(downside) > 0 else 0
    sortino = (excess_return / downside_dev) * np.sqrt(annual_factor) if downside_dev > 0 else 0
    # Max drawdown
    cum = (1 + returns_series).cumprod()
    running_max = cum.cummax()
    drawdown = (cum / running_max) - 1
    max_dd = drawdown.min()

    metrics["sharpe_ratio"] = sharpe
    metrics["sortino_ratio"] = sortino
    metrics["max_drawdown"] = max_dd

    return metrics


# -----------------------------
# Initialize portfolios
# -----------------------------
if "portfolios" not in st.session_state:
    st.session_state.portfolios = {}
    st.session_state.portfolios["Balanced 60/40"] = {"SPY": 0.6, "AGG": 0.4}
    st.session_state.portfolios["S&P500"] = {"VOO": 1.0}

# -----------------------------
# Streamlit page config
# -----------------------------
st.set_page_config(page_title="Automatic Investment", layout="wide")  # WIDE layout

# -----------------------------
# Sidebar - Page selection
# -----------------------------
page = st.sidebar.selectbox("Choose page", ["Build Portfolio", "Compare Portfolios"])

# -----------------------------
# Build Portfolio Page
# -----------------------------
if page == "Build Portfolio":
    st.header("🛠 Build Your Portfolio")

    portfolio_name = st.text_input("Portfolio Name", "My Portfolio")
    num_assets = st.number_input("Number of assets", min_value=1, max_value=20, value=3, step=1)

    portfolio = {}
    cols = st.columns(2)

    for i in range(num_assets):
        with cols[0]:
            ticker = st.text_input(f"Asset {i + 1} Ticker", key=f"ticker_{i}").strip().upper()
        with cols[1]:
            weight_pct = st.number_input(f"Weight (%)", min_value=0.1, max_value=100.0, value=100 / num_assets,
                                         step=0.1, key=f"weight_{i}")
        if ticker:
            portfolio[ticker] = weight_pct / 100  # Convert to decimal

    if st.button("Save Portfolio"):
        if portfolio_name and portfolio:
            st.session_state.portfolios[portfolio_name] = portfolio
            st.success(f"Portfolio '{portfolio_name}' saved!")

    if st.session_state.portfolios:
        st.subheader("Saved Portfolios")
        for name, data in st.session_state.portfolios.items():
            st.write(f"**{name}**: {', '.join([f'{t} ({w * 100:.1f}%)' for t, w in data.items()])}")

# -----------------------------
# Compare Portfolios Page
# -----------------------------
if page == "Compare Portfolios":
    st.header("📈 Compare Portfolios")

    # Dataset limits
    data_start = datetime(1900, 1, 1)       # earliest available in dataset
    data_end = datetime(2017, 12, 31)       # latest available in dataset

    # Ensure defaults are within dataset range
    default_start = data_end - timedelta(days=365)
    if default_start < data_start:
        default_start = data_start

    default_end = data_end

    # User selects dates with enforced limits
    start_date = st.date_input(
        "Start Date",
        value=default_start.date(),
        min_value=data_start.date(),
        max_value=data_end.date()
    )
    end_date = st.date_input(
        "End Date",
        value=default_end.date(),
        min_value=data_start.date(),
        max_value=data_end.date()
    )

    # Convert to datetime for internal calculations
    start_date_dt = datetime.combine(start_date, datetime.min.time())
    end_date_dt = datetime.combine(end_date, datetime.min.time())

    # Clamp to dataset range automatically
    if start_date_dt < data_start:
        start_date_dt = data_start
    if end_date_dt > data_end:
        end_date_dt = data_end
    if start_date_dt > end_date_dt:
        start_date_dt = end_date_dt - timedelta(days=1)

    st.info(f"Backtesting will run from **{start_date_dt.strftime('%Y-%m-%d')}** "
            f"to **{end_date_dt.strftime('%Y-%m-%d')}** (dataset limit).")

    selected_portfolios = st.multiselect("Select portfolios", list(st.session_state.portfolios.keys()))

    if st.button("Run Backtest") and selected_portfolios:
        all_tickers = set()
        for p in selected_portfolios:
            all_tickers.update(st.session_state.portfolios[p].keys())
        all_tickers = list(all_tickers)

        with st.spinner("Fetching data (from local dataset, may take a few seconds)..."):
            # Load Close prices from CSV folder
            data = batch_download(all_tickers, start=start_date_dt, end=end_date_dt)

        if data.empty:
            st.warning("No data available for the selected portfolios and date range.")
        else:
            portfolio_metrics_list = []
            pie_figs = {}
            fig = go.Figure()

            for p in selected_portfolios:
                weights = st.session_state.portfolios[p]
                tickers_in_data = [t for t in weights.keys() if t in data.columns]

                if not tickers_in_data:
                    st.warning(f"No valid tickers with data for portfolio {p}. Skipping...")
                    continue

                sub_data = data[tickers_in_data].dropna()
                if sub_data.empty:
                    st.warning(f"No data available after dropping NaNs for portfolio {p}. Skipping...")
                    continue

                # Portfolio value & daily returns
                portfolio_value, portfolio_returns = calculate_portfolio_value(sub_data, {t: weights[t]/100 for t in tickers_in_data})

                if portfolio_value.empty:
                    st.warning(f"Portfolio {p} has empty value series. Skipping...")
                    continue

                # Risk & performance metrics
                metrics = calculate_risk_metrics(portfolio_returns)
                total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
                days = (portfolio_value.index[-1] - portfolio_value.index[0]).days
                annual_return = ((1 + total_return/100)**(365/days) - 1) * 100 if days > 0 else 0
                performance_score = annual_return * (metrics.get("sharpe_ratio", 0) + metrics.get("sortino_ratio", 0)) / 2

                portfolio_metrics_list.append({
                    "Portfolio": p,
                    "Total Return (%)": total_return,
                    "Annualized Return (%)": annual_return,
                    "Sharpe Ratio": metrics.get("sharpe_ratio", 0),
                    "Sortino Ratio": metrics.get("sortino_ratio", 0),
                    "Max Drawdown": metrics.get("max_drawdown", 0),
                    "Performance Score": performance_score
                })

                # Pie chart for asset allocation
                pie_figs[p] = px.pie(
                    names=tickers_in_data,
                    values=[weights[t] for t in tickers_in_data],
                    title=f"{p} Asset Allocation"
                )

                # Portfolio growth line
                fig.add_trace(go.Scatter(x=portfolio_value.index, y=portfolio_value, mode="lines", name=p))

            # Show metrics table
            if portfolio_metrics_list:
                st.subheader("📊 Portfolio Metrics Comparison")
                metrics_df = pd.DataFrame(portfolio_metrics_list).set_index("Portfolio")
                st.dataframe(metrics_df.style.format({
                    "Total Return (%)": "{:.2f}",
                    "Annualized Return (%)": "{:.2f}",
                    "Sharpe Ratio": "{:.2f}",
                    "Sortino Ratio": "{:.2f}",
                    "Max Drawdown": "{:.2%}",
                    "Performance Score": "{:.2f}"
                }))
            else:
                st.info("No portfolios had valid data to display metrics.")

            # Show pie charts side by side
            if pie_figs:
                st.subheader("🥧 Asset Allocation")
                cols = st.columns(len(pie_figs))
                for i, (p, pie_fig) in enumerate(pie_figs.items()):
                    with cols[i]:
                        st.plotly_chart(pie_fig, use_container_width=True)

            # Portfolio growth chart
            if fig.data:
                st.subheader("📈 Portfolio Value Over Time")
                fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Value")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No valid portfolio value data to plot.")

# -----------------------------
# App Footer / Author Info
# -----------------------------
st.markdown("---")  # horizontal line
st.markdown(
    """
    <div style="text-align:center; color:gray;">
    Made with ❤️ by **Luis Ng** | 
    <a href="https://github.com/CodingLuisNg" target="_blank">GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)

