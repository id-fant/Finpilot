"""Quant / Factor Models — Step 3: decomposing returns by factor.

Step 1 regressed a stock on one factor (CAPM). Step 2 built three. This script
runs the full multi-factor regression and *decomposes* a stock's return:

  R - Rf = alpha + b_mkt*MKT + b_mom*MOM + b_lvol*LVOL + noise

The betas (factor loadings) say what the stock IS:
  high b_mkt   -> a market-sensitive name
  high b_mom   -> behaves like a momentum stock
  high b_lvol  -> behaves like a low-volatility stock
The alpha is what is left — return the factors do NOT explain. Honest alpha is
small and rare; a large alpha usually means a factor is missing from the model.

The factor-building code is copied from 02_fama_french.py — a numbered script
can't be imported as a module (its name starts with a digit), so the helper is
duplicated rather than shared.

Run:  python 03_factor_regression.py
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf
import statsmodels.api as sm

RF_DAILY = 0.065 / 252


def fetch_returns(symbols: list[str], period: str = "3y") -> pd.DataFrame:
    """Aligned daily-returns panel for a universe of tickers."""
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


def build_factors(returns: pd.DataFrame) -> pd.DataFrame:
    """MKT / MOM / LVOL factor returns — see 02_fama_french.py for the rationale."""
    formation, measure = returns.iloc[:252], returns.iloc[252:]
    momentum_score = (1 + formation).prod() - 1
    volatility_score = formation.std()
    third = max(1, len(returns.columns) // 3)

    def long_short(score: pd.Series, long_high: bool) -> pd.Series:
        ranked = score.sort_values()
        low, high = ranked.index[:third], ranked.index[-third:]
        longs, shorts = (high, low) if long_high else (low, high)
        return measure[longs].mean(axis=1) - measure[shorts].mean(axis=1)

    return pd.DataFrame({
        "MKT": measure.mean(axis=1) - RF_DAILY,
        "MOM": long_short(momentum_score, long_high=True),
        "LVOL": long_short(volatility_score, long_high=False),
    })


if __name__ == "__main__":
    universe = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
        "ASIANPAINT.NS", "MARUTI.NS",
    ]
    target = "RELIANCE.NS"

    print(f"[REGRESSION] decomposing {target} returns by factor\n")
    returns = fetch_returns(universe)
    factors = build_factors(returns)

    # The target's excess return over the SAME window the factors cover.
    measure = returns.iloc[252:]
    y = (measure[target] - RF_DAILY).reindex(factors.index).dropna()
    X = sm.add_constant(factors.reindex(y.index))
    model = sm.OLS(y, X).fit()

    alpha = model.params["const"]
    print(f"  model:  {target} - Rf  ~  alpha + b_MKT*MKT + b_MOM*MOM + b_LVOL*LVOL\n")
    print(f"  alpha (annualised) : {alpha * 252 * 100:+.2f}%")
    print(f"  R-squared          : {model.rsquared:.3f}   "
          f"(share of variance the factors explain)")
    print(f"\n  {'factor':8s}{'loading':>12}{'t-stat':>10}{'return contrib.':>18}")
    for name in factors.columns:
        beta = model.params[name]
        tstat = model.tvalues[name]
        contribution = beta * factors[name].mean() * 252 * 100
        print(f"  {name:8s}{beta:>12.3f}{tstat:>10.2f}{contribution:>17.2f}%")

    print("\n  Loadings say what the stock IS; alpha is what the factors miss.")
    print("  |t-stat| > 2  =>  that loading is statistically real, not noise.")
    print("  A large alpha is usually a missing factor, not free money.")
