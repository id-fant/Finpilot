"""Quant / Factor Models — Step 2: a Fama-French-style multi-factor model.

CAPM has one factor (the market). Decades of research found the market alone
leaves a lot unexplained — other systematic factors earn persistent premia.
Fama & French formalised this: their canonical model adds SMB (small-minus-big,
a SIZE factor) and HML (high-minus-low book-to-market, a VALUE factor); later
work adds MOM (momentum).

SMB and HML need fundamental data (market cap, book value), and the official
Fama-French factors are US-only. So this script builds three *price-based*
factors from an NSE universe instead — same machinery, no fundamentals:

  MKT   market excess return         — the equal-weight universe minus Rf.
  MOM   momentum (winners-minus-losers) — long the past winners, short losers.
  LVOL  low-minus-high volatility    — long the calm names, short the wild ones
        (the well-documented low-volatility anomaly).

A factor's "return" is the return of that long-short portfolio. Step 3 then
regresses a single stock on these factors.

Run:  python 02_fama_french.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

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
    """Build the MKT, MOM and LVOL factor return series.

    Rankings are formed on the first ~year ("formation"); the factor returns
    are measured over everything after that. The ranking never peeks at the
    window it is evaluated on — a basic guard against look-ahead bias.
    """
    formation, measure = returns.iloc[:252], returns.iloc[252:]
    momentum_score = (1 + formation).prod() - 1  # past-year total return
    volatility_score = formation.std()           # past-year volatility
    third = max(1, len(returns.columns) // 3)

    def long_short(score: pd.Series, long_high: bool) -> pd.Series:
        ranked = score.sort_values()
        low, high = ranked.index[:third], ranked.index[-third:]
        longs, shorts = (high, low) if long_high else (low, high)
        return measure[longs].mean(axis=1) - measure[shorts].mean(axis=1)

    return pd.DataFrame({
        "MKT": measure.mean(axis=1) - RF_DAILY,           # market excess return
        "MOM": long_short(momentum_score, long_high=True),  # winners - losers
        "LVOL": long_short(volatility_score, long_high=False),  # low vol - high
    })


if __name__ == "__main__":
    universe = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS",
        "ASIANPAINT.NS", "MARUTI.NS",
    ]
    print(f"[FACTORS] building MKT / MOM / LVOL from {len(universe)} NSE stocks")
    returns = fetch_returns(universe)
    factors = build_factors(returns)

    print(f"\n{'=' * 56}\n  FACTOR PERFORMANCE (measurement window)\n{'=' * 56}")
    print(f"  {'factor':8s}{'ann. return':>16}{'ann. vol':>14}{'Sharpe':>10}")
    for name in factors.columns:
        series = factors[name].dropna()
        ann_ret = series.mean() * 252
        ann_vol = series.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol else 0.0
        print(f"  {name:8s}{ann_ret * 100:>15.2f}%{ann_vol * 100:>13.2f}%"
              f"{sharpe:>10.2f}")

    print("\n  Each factor return is a long-short portfolio. A positive Sharpe")
    print("  means the factor earned a premium over this window — but factor")
    print("  premia are noisy and can vanish for years ('factor winters').")

    cumulative = (1 + factors).cumprod()
    fig, ax = plt.subplots(figsize=(11, 6))
    # matplotlib stubs declare `plot(*args)` as `Buffer | ...`; they accept
    # ndarray cleanly but not pd.Series/Index. `.to_numpy()` is the explicit,
    # zero-runtime-cost conversion — same pattern as ".NS" stripping at the
    # API boundary (LEARNINGS #61). Done here for every chart in the file.
    x = cumulative.index.to_numpy()
    for name in factors.columns:
        ax.plot(x, cumulative[name].to_numpy(), label=name, linewidth=1.3)
    ax.axhline(1, color="#6B7280", linewidth=0.5)
    ax.set_title("Fama-French-style factors — growth of 1 unit (long-short)")
    ax.set_ylabel("Cumulative factor return")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("fama_french.png", dpi=150, bbox_inches="tight")
    print("\n[CHART] saved -> fama_french.png")
    plt.close(fig)
