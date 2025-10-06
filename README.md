# Investment Portfolio Backtester

An interactive Streamlit web application to **build, backtest, and compare investment portfolios** with historical stock and ETF data. Designed and developed by **Luis Ng**.  

GitHub: [https://github.com/CodingLuisNg](https://github.com/CodingLuisNg)

---

## Description

The **Investment Portfolio Backtester** is a **Streamlit app** that allows users to:

- Build custom stock & ETF portfolios
- Backtest portfolio performance using historical data
- Compare multiple portfolios with **risk-adjusted metrics**
- Visualize portfolio growth and asset allocation

It calculates metrics such as:

- **Total Return (%)**
- **Annualized Return (%)**
- **Sharpe Ratio**
- **Sortino Ratio**
- **Max Drawdown**
- **Performance Score** (combining returns and risk management)

> ⚠️ **Note:** Historical datasets are **not included** due to size. Please download and place the required CSV/TXT files from other sources in the `dataset/` folder.
> 
> The app uses historical data from Kaggle, You can download the dataset here: [Kaggle: Price & Volume Data for All US Stocks & ETFs](https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs?resource=download)

---

## Features

- Create multiple portfolios with custom asset weights
- Automatically adjusts backtesting range based on available data (up to 2017)
- Portfolio growth line charts
- Asset allocation pie charts
- Performance scoring for risk-aware comparison

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/CodingLuisNg/investment-portfolio-backtester.git
cd investment-portfolio-backtester
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Place your historical CSV/TXT datasets in a folder named "dataset".
- Each file should be named <TICKER>.txt or <TICKER>.csv
- Must include columns: Date, Open, High, Low, Close, Volume

4. Run the app to open the app in your browser at localhost:
```bash
streamlit run main.py
```

---

## Usage

1. Build Portfolio
- Enter portfolio name
- Add tickers and weights
- Save your portfolio

2. Compare Portfolios
- Select one or more portfolios
- Set backtesting date range (automatically limited to available data)
- Click "Run Backtest"
- View portfolio metrics, growth charts, and asset allocation

---

## Author

Luis Ng

---

## License

This project is open source and free to use.
