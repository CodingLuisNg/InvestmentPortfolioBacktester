from typing import Dict, List, Tuple
from datetime import datetime
import math
import pandas as pd
import streamlit as st
import yfinance as yf


class DataModel:
    """Fetches and processes price data directly from yfinance."""
    CACHE_TTL = 24 * 3600  # 1-day cache

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
