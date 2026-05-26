"""Quant / Factor Models — Step 1: CAPM, the one-factor baseline.

The Capital Asset Pricing Model says a stock's expected excess return is
explained by ONE factor — the market:

  R_stock - Rf  =  alpha  +  beta * (R_market - Rf)  +  noise

  beta   how much the stock amplifies market moves. beta 1.2 => it tends to
         move ~20% more than the market, up and down. This is market risk.
  alpha  the average return left over AFTER accounting for market exposure.
         Positive, persistent alpha is what every active manager hunts.

We estimate both with an OLS regression of the stock's daily excess returns on
the market's (NIFTY 50, ^NSEI) daily excess returns.

Run:  python 01_factor_intro.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import statsmodels.api as sm

RF_DAILY = 0.065 / 252  # Indian 10-yr G-Sec, per trading day


def fetch_returns(symbol: str, period: str = "3y") -> pd.Series:
    """Daily returns for one ticker."""
    df = yf.Ticker(symbol).history(period=period)
    if df.empty:
        raise RuntimeError(f"No data for {symbol}")
    close = df["Close"]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    # pandas stubs reject `Series.rename(<str>)` (they want a callable Renamer);
    # at runtime a string is fine and sets `.name`. Building a new Series here
    # gives Pyright the concrete `pd.Series` return type it wants, instead of
    # the `Series | DataFrame | Unknown` that flows from `.dropna()` chaining.
    return pd.Series(close.pct_change().dropna(), name=symbol)


def capm(stock_returns: pd.Series, market_returns: pd.Series) -> dict:
    """Regress stock excess returns on market excess returns."""
    df = pd.concat([stock_returns, market_returns], axis=1).dropna()
    excess_stock = df.iloc[:, 0] - RF_DAILY
    excess_market = df.iloc[:, 1] - RF_DAILY

    model = sm.OLS(excess_stock, sm.add_constant(excess_market)).fit()
    alpha_daily, beta = model.params.iloc[0], model.params.iloc[1]
    return {
        "alpha_annual_%": round(alpha_daily * 252 * 100, 2),
        "beta": round(beta, 3),
        "r_squared": round(model.rsquared, 3),
    }


if __name__ == "__main__":
    market = fetch_returns("^NSEI")  # NIFTY 50 index
    stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS"]

    print(f"[CAPM] regressing each stock on the NIFTY 50\n")
    print(f"  {'stock':14s}{'beta':>8}{'alpha (ann.)':>16}{'R-squared':>12}")
    results = {}
    for symbol in stocks:
        try:
            res = capm(fetch_returns(symbol), market)
        except RuntimeError as e:
            print(f"  {symbol:14s} skipped ({e})")
            continue
        results[symbol] = res
        print(f"  {symbol:14s}{res['beta']:>8}{res['alpha_annual_%']:>15}%"
              f"{res['r_squared']:>12}")

    print("\n  beta > 1 amplifies the market; beta < 1 dampens it.")
    print("  R-squared is the share of the stock's moves the market explains —")
    print("  the rest is stock-specific risk, which diversification removes.")

    # Scatter for the first stock: its regression line is the CAPM fit.
    first = stocks[0]
    stock_ret = fetch_returns(first)
    df = pd.concat([stock_ret - RF_DAILY, market - RF_DAILY], axis=1).dropna()
    df.columns = ["stock", "market"]

    fig, ax = plt.subplots(figsize=(8, 7))
    # matplotlib stubs don't list pd.Series in scatter/plot signatures;
    # .to_numpy() / np.asarray() satisfy them without changing behaviour.
    ax.scatter((df["market"] * 100).to_numpy(), (df["stock"] * 100).to_numpy(),
               s=8, alpha=0.4, color="#2563EB")
    line = sm.OLS(df["stock"], sm.add_constant(df["market"])).fit()
    xs = pd.Series([df["market"].min(), df["market"].max()])
    ax.plot((xs * 100).to_numpy(),
            np.asarray(line.predict(sm.add_constant(xs))) * 100,
            color="#DC2626", linewidth=2, label=f"CAPM fit (beta {results[first]['beta']})")
    ax.axhline(0, color="#6B7280", linewidth=0.5)
    ax.axvline(0, color="#6B7280", linewidth=0.5)
    ax.set_xlabel("Market excess return (%, daily)")
    ax.set_ylabel(f"{first} excess return (%, daily)")
    ax.set_title(f"CAPM regression — {first} vs NIFTY 50")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("capm_regression.png", dpi=150, bbox_inches="tight")
    print("\n[CHART] saved -> capm_regression.png")
    plt.close(fig)
