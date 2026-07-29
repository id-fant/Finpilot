"""Quant / Portfolio Optimisation — Step 2: maximising the Sharpe ratio.

Step 1 found the efficient frontier by brute force — random sampling. Sampling
gets *close* to the best portfolio but never exactly there. This script solves
for it directly with a constrained optimiser (SciPy's SLSQP):

  maximise   Sharpe(w) = (w.mu - Rf) / sqrt(w' . Cov . w)
  subject to sum(w) = 1   and   0 <= w_i <= 1   (long-only, fully invested)

Optimisers minimise, so we minimise the *negative* Sharpe. The solution is the
**tangency portfolio** — the one point where a line drawn from the risk-free
rate is tangent to the efficient frontier, i.e. the best risk-adjusted return
the basket can offer.

Run:  python 02_sharpe_maximisation.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

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


def portfolio_stats(weights, mean, cov) -> tuple[float, float, float]:
    """Annualised return, volatility and Sharpe ratio for one weight vector."""
    ret = weights @ mean
    vol = np.sqrt(weights @ cov @ weights)
    return ret, vol, (ret - RF) / vol


def max_sharpe_weights(mean, cov) -> np.ndarray:
    """Solve for the long-only, fully-invested weights with the highest Sharpe."""
    k = len(mean)

    def neg_sharpe(w):
        ret = w @ mean
        vol = np.sqrt(w @ cov @ w)
        return -(ret - RF) / vol

    constraints = {"type": "eq", "fun": lambda w: w.sum() - 1}  # fully invested
    bounds = [(0.0, 1.0)] * k                                   # long-only
    start = np.repeat(1 / k, k)                                 # equal weight

    result = minimize(neg_sharpe, start, method="SLSQP",
                      bounds=bounds, constraints=constraints)
    if not result.success:
        print(f"  [WARN] optimiser did not converge: {result.message}")
    return result.x


def robust_covariance(returns: pd.DataFrame) -> np.ndarray:
    """Annualized Ledoit-Wolf shrinkage covariance estimate."""
    clean = returns.dropna()
    if clean.empty:
        raise ValueError("returns contain no complete observations")
    return LedoitWolf().fit(clean.to_numpy()).covariance_ * TRADING_DAYS


def equal_risk_contribution_weights(cov) -> np.ndarray:
    """Long-only weights whose assets contribute equal portfolio risk."""
    cov = np.asarray(cov, dtype=float)
    k = len(cov)

    def objective(w):
        marginal = cov @ w
        contributions = w * marginal
        total = contributions.sum()
        if total <= 0:
            return 1e6
        shares = contributions / total
        return float(np.sum((shares - 1 / k) ** 2))

    result = minimize(
        objective,
        np.repeat(1 / k, k),
        method="SLSQP",
        bounds=[(1e-8, 1.0)] * k,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if not result.success:
        print(f"  [WARN] risk-parity optimiser did not converge: {result.message}")
    return result.x / result.x.sum()


if __name__ == "__main__":
    basket = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS",
              "INFY.NS", "ITC.NS", "LT.NS"]
    print(f"[MAX SHARPE] solving for the tangency portfolio ({len(basket)} stocks)")
    returns = fetch_returns(basket)
    # np.asarray(series) accepts a Series directly; skipping `.values` avoids
    # Pyright's complaint about scalar branches in the mean() type union.
    # See 01_markowitz.py for the same pattern.
    mean = np.asarray(returns.mean()) * TRADING_DAYS
    cov = robust_covariance(returns)

    optimal = max_sharpe_weights(mean, cov)
    risk_parity = equal_risk_contribution_weights(cov)
    equal = np.repeat(1 / len(returns.columns), len(returns.columns))

    print(f"\n  {'portfolio':16s}{'return':>10}{'vol':>10}{'Sharpe':>10}")
    for label, w in [
        ("equal-weight", equal),
        ("risk-parity", risk_parity),
        ("max-Sharpe", optimal),
    ]:
        ret, vol, sharpe = portfolio_stats(w, mean, cov)
        print(f"  {label:16s}{ret * 100:>9.2f}%{vol * 100:>9.2f}%{sharpe:>10.2f}")

    print("\n  Max-Sharpe weights:")
    for symbol, w in zip(returns.columns, optimal):
        print(f"    {symbol:14s} {w * 100:5.1f}%")

    print("\n  Equal-risk-contribution weights:")
    for symbol, w in zip(returns.columns, risk_parity):
        print(f"    {symbol:14s} {w * 100:5.1f}%")

    print("\n  This is the tangency portfolio — the exact point the random")
    print("  search in 01_markowitz.py could only approximate. Caveat: it is")
    print("  optimal for the PAST. Mean returns are hard to estimate, so live")
    print("  performance degrades — which is why naive equal-weight endures.")
