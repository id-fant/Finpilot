"""Quant / Mean Reversion — Step 2: cointegration.

Two stocks can each be non-stationary — their prices wander — and yet move
*together*, so a specific linear combination of them IS stationary. Such a pair
is **cointegrated**, and that stationary combination is the **spread** you
actually trade.

Engle-Granger two-step test:
  1. Regress price_y on price_x (OLS). The slope is the hedge ratio.
  2. Run the ADF test on the regression residuals (the spread). A stationary
     spread means the pair is cointegrated.

`statsmodels.tsa.stattools.coint` wraps both steps and returns a p-value:
  p-value < 0.05 -> cointegrated -> the spread mean-reverts -> tradeable.

Correlation is NOT cointegration. Correlation measures returns moving together
day to day; cointegration measures prices not drifting apart over the long run.
You can have either without the other — pairs trading needs cointegration.

Run:  python 02_cointegration.py
"""
from __future__ import annotations

from itertools import combinations
from typing import cast

import pandas as pd
import yfinance as yf
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint


def fetch_closes(symbols: list[str], period: str = "3y") -> pd.DataFrame:
    """Aligned daily-Close panel for several tickers."""
    frames = {}
    for symbol in symbols:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            print(f"  [WARN] no data for {symbol}")
            continue
        frames[symbol] = df["Close"]
    prices = pd.DataFrame(frames)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices.dropna()


def hedge_ratio(y: pd.Series, x: pd.Series) -> float:
    """OLS slope of y on x — units of x that hedge one unit of y."""
    model = sm.OLS(y, sm.add_constant(x)).fit()
    return float(model.params.iloc[1])


def scan_pairs(prices: pd.DataFrame) -> pd.DataFrame:
    """Test every pair in the basket for cointegration, ranked by p-value."""
    rows = []
    for a, b in combinations(prices.columns, 2):
        # Pyright sees `prices[col]` as `Series | DataFrame` (duplicate
        # columns could yield DataFrame); cast pins it to Series. Pyrefly
        # already narrows correctly and would flag the cast as redundant —
        # the targeted ignore keeps both checkers happy.
        ya = cast("pd.Series", prices[a])  # pyrefly: ignore[redundant-cast]
        yb = cast("pd.Series", prices[b])  # pyrefly: ignore[redundant-cast]
        _, p_value, _ = coint(ya, yb)
        rows.append({
            "pair": f"{a} / {b}",
            # statsmodels stubs union p_value as float|ndarray; at runtime it
            # is always a scalar for this 2-sample form. Coerce for round().
            "p_value": round(float(p_value), 4),
            "hedge_ratio": round(hedge_ratio(ya, yb), 3),
            "cointegrated": p_value < 0.05,
        })
    return pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)


if __name__ == "__main__":
    # Stocks in the same sector are the natural hunting ground — they share
    # the macro drivers that keep a spread tethered.
    basket = ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
              "AXISBANK.NS", "KOTAKBANK.NS"]
    print(f"[COINTEGRATION] scanning {len(basket)} banking stocks, all pairs")

    prices = fetch_closes(basket)
    results = scan_pairs(prices)

    print(f"\n{'=' * 60}\n  ENGLE-GRANGER COINTEGRATION (ranked by p-value)\n{'=' * 60}")
    print(results.to_string(index=False))

    hits = results[results["cointegrated"]]
    if hits.empty:
        print("\n  No cointegrated pairs at the 5% level — try another sector.")
    else:
        best = hits.iloc[0]
        print(f"\n  Best pair: {best['pair']}  (p-value {best['p_value']}, "
              f"hedge ratio {best['hedge_ratio']})")
        print("  Step 3 (03_pairs_trading.py) trades the spread of that pair.")
