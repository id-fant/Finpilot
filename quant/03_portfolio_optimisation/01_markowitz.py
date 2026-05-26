"""Quant / Portfolio Optimisation — Step 1: the Markowitz efficient frontier.

Harry Markowitz's insight (1952): a portfolio is not just its assets, it is
their *covariance*. Combining assets that don't move together lowers risk for
free — diversification is the only genuine "free lunch" in investing.

For every level of risk there is a portfolio with the highest possible return;
that set of best-in-class portfolios is the **efficient frontier**. This script
draws it by simulating thousands of random weightings and plotting risk vs
return — the upper-left edge of the cloud IS the frontier.

Run:  python 01_markowitz.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

RF = 0.065
TRADING_DAYS = 252


def fetch_returns(symbols: list[str], period: str = "3y") -> pd.DataFrame:
    """Aligned daily-returns panel for a basket of tickers."""
    frames = {}
    for symbol in symbols:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            print(f"  [WARN] no data for {symbol}")
            continue
        frames[symbol] = df["Close"]
    prices = pd.DataFrame(frames)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices.dropna().pct_change().dropna()


def random_portfolios(returns: pd.DataFrame, n: int = 20_000):
    """Simulate n random long-only weightings; return weights, return, vol, Sharpe."""
    # `np.asarray(series)` accepts a Series directly and gives an ndarray —
    # skipping `.values` avoids Pyright's complaint that `returns.mean()`'s
    # type union includes scalar `float|int` (no `.values` attribute).
    mean = np.asarray(returns.mean()) * TRADING_DAYS
    cov = np.asarray(returns.cov()) * TRADING_DAYS
    k = len(mean)

    rng = np.random.default_rng(42)
    weights = rng.random((n, k))
    weights /= weights.sum(axis=1, keepdims=True)  # each row sums to 1

    rets = weights @ mean
    # Per-portfolio variance w' . Cov . w, vectorised across all n rows.
    vols = np.sqrt(np.einsum("ij,jk,ik->i", weights, cov, weights))
    sharpes = (rets - RF) / vols
    return weights, rets, vols, sharpes


if __name__ == "__main__":
    basket = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS",
              "INFY.NS", "ITC.NS", "LT.NS"]
    print(f"[MARKOWITZ] simulating 20,000 random portfolios of {len(basket)} stocks")
    returns = fetch_returns(basket)
    weights, rets, vols, sharpes = random_portfolios(returns)

    best = int(sharpes.argmax())   # max Sharpe — the tangency portfolio
    safe = int(vols.argmin())      # minimum variance — the calmest portfolio

    def show(label: str, idx: int) -> None:
        print(f"\n  {label}")
        print(f"    return {rets[idx] * 100:.2f}%  |  vol {vols[idx] * 100:.2f}%"
              f"  |  Sharpe {sharpes[idx]:.2f}")
        for symbol, w in zip(returns.columns, weights[idx]):
            print(f"      {symbol:14s} {w * 100:5.1f}%")

    show("Max-Sharpe portfolio", best)
    show("Min-variance portfolio", safe)

    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(vols * 100, rets * 100, c=sharpes, cmap="viridis",
                         s=6, alpha=0.6)
    ax.scatter(vols[best] * 100, rets[best] * 100, marker="*", s=420,
               color="#DC2626", edgecolor="white", label="max Sharpe", zorder=5)
    ax.scatter(vols[safe] * 100, rets[safe] * 100, marker="*", s=420,
               color="#2563EB", edgecolor="white", label="min variance", zorder=5)
    fig.colorbar(scatter, label="Sharpe ratio")
    ax.set_xlabel("Annualised volatility (%)")
    ax.set_ylabel("Annualised return (%)")
    ax.set_title("Markowitz efficient frontier — 20,000 random portfolios")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("markowitz_frontier.png", dpi=150, bbox_inches="tight")
    print("\n[CHART] saved -> markowitz_frontier.png")
    print("\n  The upper-left edge of the cloud is the efficient frontier: for")
    print("  each level of risk, the most return the basket can deliver.")
    plt.close(fig)
