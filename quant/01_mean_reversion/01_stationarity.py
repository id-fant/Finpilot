"""Quant / Mean Reversion — Step 1: stationarity.

A mean-reversion strategy bets that a series returns to its average. That only
works if the series HAS a stable average — i.e. it is *stationary*. Stock
prices are not: they trend and wander (a random walk, with a "unit root").
Daily returns usually are stationary.

This script runs the Augmented Dickey-Fuller (ADF) test on a price series and
on its returns, and shows why mean-reversion traders work with returns and
spreads, never with raw prices.

ADF null hypothesis: "the series has a unit root" (it is non-stationary).
  p-value <  0.05  -> reject the null -> stationary     -> mean-reverts.
  p-value >= 0.05  -> fail to reject  -> non-stationary -> trends / wanders.

Run:  python 01_stationarity.py
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller


def fetch_close(symbol: str, period: str = "3y") -> pd.Series:
    """Daily Close for one ticker, timezone stripped."""
    df = yf.Ticker(symbol).history(period=period)
    if df.empty:
        raise RuntimeError(f"No data for {symbol}")
    # Pyright sees `df["Close"]` as `Series | DataFrame` (duplicate-column
    # paranoia) and also rejects `Series.rename(<str>)`. Building a fresh
    # `pd.Series` with `name=` collapses both issues in one line.
    close_raw = df["Close"]
    return pd.Series(
        close_raw.values, name=symbol,
        index=pd.to_datetime(close_raw.index).tz_localize(None),
    )


def adf_test(series: pd.Series, label: str) -> dict:
    """Run the ADF test on one series and print a verdict."""
    series = series.dropna()
    # statsmodels has multiple overloads for adfuller's return tuple; the
    # default (autolag set) returns the 6-tuple unpacked here. The stubs
    # union all overloads, so type checkers can't narrow — suppress the
    # spurious "tuple of size 4/5 into 6" complaints from both Pyrefly and
    # Pyright (the IDE uses Pyright via Pylance).
    # pyrefly: ignore[bad-unpacking]
    stat, p_value, _, _, crit, _ = adfuller(series)  # pyright: ignore[reportAssignmentType]
    stationary = p_value < 0.05
    print(f"\n  {label}")
    print(f"    ADF statistic : {stat:>10.3f}")
    print(f"    p-value       : {p_value:>10.4f}")
    print(f"    1% / 5% crit  : {crit['1%']:.3f} / {crit['5%']:.3f}")
    print(f"    verdict       : "
          f"{'STATIONARY (mean-reverts)' if stationary else 'NON-STATIONARY (trends)'}")
    return {"label": label, "adf_stat": stat, "p_value": p_value,
            "stationary": stationary}


if __name__ == "__main__":
    symbol = "RELIANCE.NS"
    print(f"[STATIONARITY] testing {symbol} — price vs returns")

    close = fetch_close(symbol)
    returns = close.pct_change().dropna()

    adf_test(close, f"{symbol} Close price")
    adf_test(returns, f"{symbol} daily returns")

    print("\n  Takeaway: the price has a unit root — it wanders, so 'it has")
    print("  gone up, it must come down' is not a strategy. Returns are")
    print("  stationary; so is the spread of a cointegrated pair (next script).")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7))
    # matplotlib stubs don't list pd.Series/Index in plot/axhline signatures;
    # .to_numpy() / float() convert at the boundary, no runtime change.
    ax1.plot(close.index.to_numpy(), close.to_numpy(), color="#2563EB", linewidth=1)
    ax1.set_title(f"{symbol} Close — non-stationary (trends, wanders)")
    ax1.grid(alpha=0.3)
    ax2.plot(returns.index.to_numpy(), returns.to_numpy(), color="#10B981", linewidth=0.6)
    # pyrefly: ignore[unnecessary-type-conversion]
    ax2.axhline(float(returns.mean()), color="#DC2626", linewidth=1, label="mean")
    ax2.set_title(f"{symbol} daily returns — stationary (stable mean & variance)")
    ax2.legend()
    ax2.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("stationarity.png", dpi=150, bbox_inches="tight")
    print("\n[CHART] saved -> stationarity.png")
    plt.close(fig)
