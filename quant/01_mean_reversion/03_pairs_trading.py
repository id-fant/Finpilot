"""Quant / Mean Reversion — Step 3: a pairs-trading strategy.

Cointegration (step 2) found pairs whose spread is stationary. This script
trades that spread:

  spread  = price_y - hedge_ratio * price_x
  z-score = (spread - rolling_mean) / rolling_std

The spread oscillates around zero. The rules:
  z >  +entry  -> spread is rich  -> SHORT it (sell y, buy x)
  z <  -entry  -> spread is cheap -> LONG  it (buy y, sell x)
  |z| < exit   -> spread reverted -> CLOSE the position

This is **market-neutral**: long one stock and short the other, so a market-
wide move roughly cancels. The bet is purely on the pair converging.

It picks the most strongly cointegrated pair in a basket automatically, so the
script always trades something sensible.

Run:  python 03_pairs_trading.py
"""
from __future__ import annotations

from itertools import combinations
from typing import cast

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

WINDOW = 30   # rolling window for the z-score
ENTRY = 2.0   # open a position once |z| exceeds this
EXIT = 0.5    # close it once |z| falls back inside this


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


def best_pair(prices: pd.DataFrame) -> tuple[str, str, float]:
    """Return the most strongly cointegrated pair (lowest p-value)."""
    best: tuple[str, str, float] | None = None
    for a, b in combinations(prices.columns, 2):
        _, p_value, _ = coint(prices[a], prices[b])
        # coint's stubs union p_value as float|ndarray; runtime is scalar.
        p_scalar = float(p_value)
        if best is None or p_scalar < best[2]:
            best = (a, b, p_scalar)
    if best is None:
        raise RuntimeError("need at least two columns to form a pair")
    return best


def hedge_ratio(y: pd.Series, x: pd.Series) -> float:
    """OLS slope of y on x."""
    return float(sm.OLS(y, sm.add_constant(x)).fit().params.iloc[1])


def generate_positions(z: pd.Series, entry: float = ENTRY,
                       exit: float = EXIT) -> pd.Series:
    """Stateful entry/exit: +1 long the spread, -1 short it, 0 flat.

    Position is stateful — once open it is held until the z-score reverts
    inside `exit`. The hysteresis (entry far out, exit near zero) stops the
    strategy flickering in and out around the threshold.
    """
    positions, current = [], 0
    for value in z:
        if current == 0:
            if value > entry:
                current = -1          # spread rich -> short it
            elif value < -entry:
                current = 1           # spread cheap -> long it
        elif current == 1 and value >= -exit:
            current = 0               # long spread reverted -> close
        elif current == -1 and value <= exit:
            current = 0               # short spread reverted -> close
        positions.append(current)
    return pd.Series(positions, index=z.index)


if __name__ == "__main__":
    basket = ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
              "AXISBANK.NS", "KOTAKBANK.NS"]
    print(f"[PAIRS] scanning {len(basket)} banking stocks for the best pair...")
    prices = fetch_closes(basket)

    y_sym, x_sym, p_value = best_pair(prices)
    print(f"[PAIRS] trading {y_sym} vs {x_sym}  (cointegration p-value {p_value:.4f})")

    # Pyright sees `prices[col]` as `Series | DataFrame`; cast pins it.
    # See 02_cointegration.py for the same pattern.
    y = cast("pd.Series", prices[y_sym])  # pyrefly: ignore[redundant-cast]
    x = cast("pd.Series", prices[x_sym])  # pyrefly: ignore[redundant-cast]
    beta = hedge_ratio(y, x)
    spread = y - beta * x
    z = (spread - spread.rolling(WINDOW).mean()) / spread.rolling(WINDOW).std()

    positions = generate_positions(z.fillna(0))

    # Market-neutral return: long y, short beta*x, normalised by gross exposure.
    # positions.shift(1) — you trade on yesterday's signal, never today's close.
    ret_y, ret_x = y.pct_change(), x.pct_change()
    gross = 1 + abs(beta)
    spread_return = (ret_y - beta * ret_x) / gross
    strategy_return = positions.shift(1).fillna(0) * spread_return
    equity = (1 + strategy_return).cumprod()

    daily = strategy_return.dropna()
    # pyright sees `.sum()` as `Series | int`; the int() pin keeps the f-string
    # format clean. Pyrefly already narrows here — suppress for parity.
    # pyrefly: ignore[unnecessary-type-conversion]
    trades = int((positions.diff().abs() > 0).sum())
    total = (equity.iloc[-1] - 1) * 100
    sharpe = daily.mean() / daily.std() * np.sqrt(252) if daily.std() else 0.0

    print(f"\n  hedge ratio        : {beta:.3f}")
    print(f"  position changes   : {trades}")
    print(f"  total return       : {total:+.2f}%")
    print(f"  annualised Sharpe  : {sharpe:.2f}")
    print("\n  Market-neutral: profit comes from the pair converging, not from")
    print("  market direction. The risk is regime change — if cointegration")
    print("  stops holding, the spread stops reverting and the edge is gone.")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
    # matplotlib stubs don't list pd.Series/Index in plot signatures;
    # .to_numpy() converts at the boundary.
    ax1.plot(z.index.to_numpy(), z.to_numpy(), color="#2563EB", linewidth=0.8)
    ax1.axhline(ENTRY, color="#DC2626", linestyle="--", linewidth=0.8)
    ax1.axhline(-ENTRY, color="#DC2626", linestyle="--", linewidth=0.8)
    ax1.axhline(0, color="#6B7280", linewidth=0.5)
    ax1.set_title(f"Spread z-score — {y_sym} vs {x_sym}  (+/-{ENTRY} = entry)")
    ax1.grid(alpha=0.3)
    ax2.plot(equity.index.to_numpy(), equity.to_numpy(), color="#10B981", linewidth=1.2)
    ax2.axhline(1, color="#6B7280", linewidth=0.5)
    ax2.set_title("Pairs strategy — growth of 1 unit")
    ax2.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("pairs_trading.png", dpi=150, bbox_inches="tight")
    print("\n[CHART] saved -> pairs_trading.png")
    plt.close(fig)
