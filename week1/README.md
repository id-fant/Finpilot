# FinPilot — Week 1: Quantitative Foundations

A data pipeline and strategy engine: fetch Indian stock data, compute technical
indicators, generate buy/sell signals, and backtest them with overfitting
prevention.

## Files (run in order)

| File | What it does |
|------|--------------|
| `01_data_foundations.py` | OHLCV, returns, moving averages, Sharpe, drawdown, volume |
| `02_technical_indicators.py` | RSI, MACD, Bollinger Bands, confluence signals |
| `03_backtesting.py` | vectorbt backtest, parameter optimisation, walk-forward |

## Setup

```bash
cd week_1
pip install -r requirements.txt
python 01_data_foundations.py
python 02_technical_indicators.py
python 03_backtesting.py
```

## Notes
- Indicators in `02` are implemented from scratch (no pandas-ta) — its column
  names drift between versions.
- `01` fetches tickers concurrently; `03` hoists the version-independent RSI
  computation out of the optimisation grid.
- Stocks used: NSE tickers with the `.NS` suffix (RELIANCE, TCS, HDFCBANK,
  INFY, ICICIBANK, WIPRO).

> Concept explanations and interview notes: see `../LEARNINGS.md`.
