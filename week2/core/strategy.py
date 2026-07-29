"""Strategy engine — pure Python, deliberately Django-free.

WHY no Django imports here: this engine is the heart of FinPilot's logic.
Keeping it free of the ORM means it is (a) unit-testable without a database,
(b) reusable from Celery tasks, management commands and notebooks, and
(c) portable — the fastapi_spike/ project serves this exact logic.

INTERVIEW — clean architecture / "ports and adapters": when asked how you
separate business logic from a framework, point here. The web framework and
the database are ADAPTERS around a framework-agnostic CORE. Mixing ORM calls
into indicator maths is where Django projects become untestable.

(`logging` is standard library, not a framework — using it here does not
compromise the engine's framework-free design; it just makes it observable.)

Ported from week1/02_technical_indicators.py.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import cast

import numpy as np
import pandas as pd

from core.quant_math import ewma_annualized_volatility, trend_regime

# Logger name is "core.strategy" — routed via the "core" logger.
logger = logging.getLogger(__name__)

RSI_PERIOD = 14
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65


def _rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Compute the Relative Strength Index (0-100) for a close-price series.

    WHY hand-rolled instead of pandas-ta: pandas-ta's output COLUMN NAMES drift
    between versions (e.g. BBU_20_2.0 vs BBU_20_2.0_2.0), which silently breaks
    downstream code. A five-line formula we control is more stable than the
    dependency. (pandas-ta stays in requirements.txt as a reference / fallback.)

    Args:
        close: series of closing prices.
        period: smoothing window, conventionally 14.

    Returns:
        RSI series aligned to `close`.
    """
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    # `.ewm().mean()` is stubbed as `float | Series`; for a Series input it is
    # always Series at runtime, so `.fillna()` exists. Pyright cannot narrow.
    return (100 - 100 / (1 + rs)).fillna(100)  # pyright: ignore[reportAttributeAccessIssue]


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Attach RSI, MACD and Bollinger Bands to an OHLCV frame.

    Args:
        df: OHLCV DataFrame as returned by core.data.fetch_ohlcv.

    Returns:
        A copy of `df` with these columns added: rsi, macd, macd_signal,
        macd_hist, bb_mid, bb_upper, bb_lower.
    """
    df = df.copy()
    # pandas stubs union `df[col]` as `Series | DataFrame`; always Series for
    # a single string key. Pin it so downstream `_rsi(close)` type-checks.
    close = cast("pd.Series", df["Close"])  # pyrefly: ignore[redundant-cast]
    logger.debug("compute_indicators: %d bars (RSI, MACD, Bollinger Bands)",
                 len(df))

    # RSI — momentum oscillator.
    df["rsi"] = _rsi(close)

    # MACD — fast EMA minus slow EMA, with a signal line and histogram.
    # WHY EMA, not SMA: an exponential average weights recent prices more
    # heavily, so MACD reacts faster to a change in trend.
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands — a 20-day SMA plus/minus 2 standard deviations.
    # The bands widen when volatile and pinch ("squeeze") when calm.
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    df["bb_mid"] = sma20
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20

    return df


def _clean(value: float) -> float | None:
    """Convert a possibly-NaN float into a JSON/DB-safe float or None."""
    # Pyright sees `value` as `float | Series` (pandas mean()'s scalar/series
    # union); the float() pin keeps round() happy. Pyrefly already narrows to
    # float here and flags it as redundant — suppress for parity.
    # pyrefly: ignore[unnecessary-type-conversion]
    return None if pd.isna(value) else round(float(value), 4)


def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    benchmark: pd.DataFrame | pd.Series | None = None,
    apply_trend_filter: bool = True,
    volatility_halflife: int = 20,
) -> dict:
    """Evaluate the strategy on the most recent bar and return a signal.

    Uses 3-indicator CONFLUENCE: one indicator firing is noise; two or more
    agreeing is a real signal. A directional call (BUY/SELL) needs >= 2 of 3
    votes. This cuts the false-positive rate of any single indicator.

    Args:
        df: OHLCV DataFrame (indicators are computed internally).
        symbol: the ticker — copied into the result for the caller's convenience.
        benchmark: optional benchmark OHLCV frame or close series.
        apply_trend_filter: reject BUYs in a confirmed bear regime when true.
        volatility_halflife: EWMA half-life used by execution-time sizing.

    Returns:
        dict with keys: symbol, date, signal, rsi, macd, macd_signal, price,
        reason. `signal` is one of "BUY" / "SELL" / "HOLD".
    """
    logger.debug("generate_signal(%s): evaluating %d input bars", symbol, len(df))
    indicators = compute_indicators(df)
    close = cast("pd.Series", indicators["Close"])
    benchmark_close = None
    if isinstance(benchmark, pd.DataFrame) and "Close" in benchmark:
        benchmark_close = cast("pd.Series", benchmark["Close"])
    elif isinstance(benchmark, pd.Series):
        benchmark_close = benchmark
    regime = trend_regime(close, benchmark_close)
    annualized_vol = ewma_annualized_volatility(
        close.pct_change(), halflife=volatility_halflife
    )
    last = indicators.iloc[-1]
    # `Index.__getitem__` returns `Index | scalar` per stubs; on a
    # DatetimeIndex the scalar is always a Timestamp (which has .date()).
    today_date: dt.date = pd.Timestamp(indicators.index[-1]).date()  # pyright: ignore[reportArgumentType]

    # WHY this guard: detecting a MACD crossover needs a PREVIOUS bar to compare
    # against. With fewer than 2 rows we cannot evaluate — return a safe HOLD.
    if len(indicators) < 2:
        logger.warning("generate_signal(%s): only %d bar(s) of data — cannot "
                        "evaluate indicators, returning HOLD", symbol, len(indicators))
        return {
            "symbol": symbol, "date": today_date, "signal": "HOLD",
            "rsi": None, "macd": None, "macd_signal": None,
            "price": round(float(last["Close"]), 2),
            "reason": "HOLD (insufficient history to evaluate indicators)",
            "buy_votes": 0, "sell_votes": 0,
            "annualized_vol": annualized_vol,
            "trend_regime": regime["label"],
            "trend_score": regime["score"],
        }

    today = indicators.iloc[-1]
    yesterday = indicators.iloc[-2]
    reasons: list[str] = []
    buy_votes = sell_votes = 0

    # Vote 1 — RSI extremes.
    if today["rsi"] < RSI_OVERSOLD:
        buy_votes += 1
        reasons.append(f"RSI {today['rsi']:.0f} oversold (<{RSI_OVERSOLD})")
    elif today["rsi"] > RSI_OVERBOUGHT:
        sell_votes += 1
        reasons.append(f"RSI {today['rsi']:.0f} overbought (>{RSI_OVERBOUGHT})")

    # Vote 2 — MACD crossover (compare today's relation to yesterday's).
    crossed_up = (yesterday["macd"] < yesterday["macd_signal"]
                  and today["macd"] > today["macd_signal"])
    crossed_down = (yesterday["macd"] > yesterday["macd_signal"]
                    and today["macd"] < today["macd_signal"])
    if crossed_up:
        buy_votes += 1
        reasons.append("MACD crossed above its signal line")
    elif crossed_down:
        sell_votes += 1
        reasons.append("MACD crossed below its signal line")

    # Vote 3 — Bollinger Band breach.
    if pd.notna(today["bb_lower"]) and today["Close"] < today["bb_lower"]:
        buy_votes += 1
        reasons.append("price below the lower Bollinger Band")
    elif pd.notna(today["bb_upper"]) and today["Close"] > today["bb_upper"]:
        sell_votes += 1
        reasons.append("price above the upper Bollinger Band")

    if buy_votes >= 2 and buy_votes > sell_votes:
        signal = "BUY"
    elif sell_votes >= 2 and sell_votes > buy_votes:
        signal = "SELL"
    else:
        signal = "HOLD"

    # DEBUG the vote breakdown — this is the line that answers "why did this
    # stock get this signal?" when a result looks wrong at runtime.
    logger.debug("generate_signal(%s) %s: buy_votes=%d sell_votes=%d -> %s "
                 "(rsi=%.1f, close=%.2f)", symbol, today_date, buy_votes,
                 sell_votes, signal, today["rsi"], today["Close"])

    detail = "; ".join(reasons) if reasons else "no indicator extremes"
    if (signal == "BUY" and apply_trend_filter
            and regime["eligible"] is False):
        signal = "HOLD"
        detail += "; BUY rejected by long-term trend/relative-momentum filter"
    reason = f"{signal}: {detail}" if signal != "HOLD" else f"HOLD ({detail})"

    return {
        "symbol": symbol,
        "date": today_date,
        "signal": signal,
        "rsi": _clean(today["rsi"]),
        "macd": _clean(today["macd"]),
        "macd_signal": _clean(today["macd_signal"]),
        "price": round(float(today["Close"]), 2),
        "reason": reason,
        # Vote counts feed the meta-labeling ML gate (core/ml_features.py) —
        # 3-of-3 confluence is a stronger setup than 2-of-3, and the model
        # should know which it is looking at.
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "annualized_vol": (
            None if annualized_vol is None else round(annualized_vol, 6)
        ),
        "trend_regime": regime["label"],
        "trend_score": regime["score"],
    }
