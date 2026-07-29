"""Feature engineering for the meta-labeling ML gate — framework-free.

WHY this module exists (train/serve parity): the #1 silent killer of deployed
ML is training on features computed one way and serving features computed
another. Both the dataset builder (quant/04_meta_labeling/01_build_dataset.py)
and the live gate (core/ml_gate.py) import THIS file, so a feature can only
ever mean one thing.

WHY these features: each one encodes a regime the RSI-confluence strategy is
known to behave differently in (see interview_prep/finance_quant.md Q13):
  rsi, macd_hist, bb_pctb — the raw indicator state at signal time
  dist_sma200            — the trend filter as a *feature*: mean-reversion
                           BUYs below the 200-DMA fight the trend
  vol20, vol_ratio       — volatility level and regime (20d vs 100d): a
                           2%-stop trade behaves differently at 30% vol
  buy_votes              — 2-of-3 vs 3-of-3 confluence strength
  dow                    — day-of-week (weekly settlement/flow seasonality)

INTERVIEW — meta-labeling (López de Prado): the model does NOT predict
prices. It predicts whether OUR OWN strategy's signal will clear costs —
a much easier, better-posed problem than forecasting returns.
"""
from __future__ import annotations

import pandas as pd

from core.strategy import (
    RSI_OVERBOUGHT, RSI_OVERSOLD, compute_indicators,
)

# Order matters — the trained model consumes vectors in exactly this order.
FEATURES = [
    "rsi", "macd_hist", "bb_pctb", "dist_sma200",
    "vol20", "vol_ratio", "buy_votes", "dow",
]

# Barrier geometry — MUST mirror the live exit rules in
# scripts/run_trading_session.py (stop 2%, target 4%, 5-day timeout).
# Training on the exact lifecycle the supervisor executes is what makes the
# label mean something in production.
STOP_PCT = 0.02
TARGET_PCT = 0.04
HORIZON_BARS = 5


def enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV frame -> indicators (core.strategy) + the ML feature columns.

    Rows before the longest lookback (SMA-200) carry NaNs; the dataset
    builder skips them and HistGradientBoosting tolerates them at serve time.
    """
    ind = compute_indicators(df)
    close = ind["Close"]

    band_width = ind["bb_upper"] - ind["bb_lower"]
    # %B: where price sits inside the Bollinger channel (0 = lower band,
    # 1 = upper). Guard the zero-width squeeze case.
    ind["bb_pctb"] = (close - ind["bb_lower"]) / band_width.replace(0, pd.NA)

    sma200 = close.rolling(200).mean()
    sma50 = close.rolling(50).mean()
    ind["dist_sma200"] = close / sma200 - 1
    ind["trend_ok"] = (
        (close > sma200)
        & (sma50 > sma200)
        & (sma200 > sma200.shift(20))
    )

    ret = close.pct_change()
    ind["vol20"] = ret.rolling(20).std()
    ind["vol_ratio"] = ind["vol20"] / ret.rolling(100).std()

    # pandas stubs see a plain Index here; the runtime index is a
    # DatetimeIndex (core.data normalises it), which has dayofweek.
    # pyrefly: ignore[missing-attribute]
    ind["dow"] = ind.index.dayofweek  # pyright: ignore[reportAttributeAccessIssue]
    return ind


def vectorized_votes(ind: pd.DataFrame) -> pd.DataFrame:
    """Per-bar confluence votes for a whole frame — one pass, no Python loop.

    MIRRORS core.strategy.generate_signal's three rules exactly (RSI extreme,
    MACD crossover, Bollinger breach). generate_signal evaluates only the
    LAST bar — fine for the daily task, O(n^2) for a 5-year scan. This
    vectorized twin exists for the scan; test_ml_features.py asserts the two
    implementations agree so they cannot drift apart silently.

    Returns `ind` with buy_votes / sell_votes / vec_signal columns added.
    """
    rsi = ind["rsi"]
    macd, sig = ind["macd"], ind["macd_signal"]
    close = ind["Close"]

    buy_rsi = rsi < RSI_OVERSOLD
    sell_rsi = rsi > RSI_OVERBOUGHT
    crossed_up = (macd.shift(1) < sig.shift(1)) & (macd > sig)
    crossed_down = (macd.shift(1) > sig.shift(1)) & (macd < sig)
    buy_bb = ind["bb_lower"].notna() & (close < ind["bb_lower"])
    sell_bb = ind["bb_upper"].notna() & (close > ind["bb_upper"])

    ind = ind.copy()
    ind["buy_votes"] = (buy_rsi.astype(int) + crossed_up.astype(int)
                        + buy_bb.astype(int))
    ind["sell_votes"] = (sell_rsi.astype(int) + crossed_down.astype(int)
                         + sell_bb.astype(int))

    # Train on the same long-term trend regime accepted by live generation.
    # Warm-up rows are False here and are skipped by the dataset builder.
    trend_warmed_up = ind["Close"].rolling(200).mean().shift(20).notna()
    trend_eligible = ind["trend_ok"] | ~trend_warmed_up
    buy = (
        (ind["buy_votes"] >= 2)
        & (ind["buy_votes"] > ind["sell_votes"])
        & trend_eligible
    )
    sell = (ind["sell_votes"] >= 2) & (ind["sell_votes"] > ind["buy_votes"])
    ind["vec_signal"] = "HOLD"
    ind.loc[buy, "vec_signal"] = "BUY"
    ind.loc[sell, "vec_signal"] = "SELL"
    # Bar 0 needs no special-casing to mirror generate_signal's hard HOLD:
    # every vote is structurally False there (RSI is NaN inside its warm-up,
    # shift(1) makes both crossover tests NaN→False, and the Bollinger bands
    # are NaN for 19 bars) — so 0 votes ⇒ HOLD falls out of the rules.
    return ind


def feature_vector(ind: pd.DataFrame, i: int) -> dict[str, float]:
    """The FEATURES dict for bar `i` of an enriched+voted frame.

    Values may be NaN near the start of the frame (lookback warm-up) —
    callers decide whether to skip (training) or tolerate (HGB serving).
    """
    row = ind.iloc[i]
    return {name: float(row[name]) for name in FEATURES}
