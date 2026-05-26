"""Unit tests for the strategy engine — no Django, no DB, no network.

These run on the framework-free `core.strategy` module directly. WHY this
matters: the engine is the BUSINESS LOGIC. If it breaks silently, every
downstream layer (the task, the API, the dashboard) is wrong in a way that
no integration test would catch. Pure-function tests on the engine are the
cheapest, fastest regression net you can have.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy import compute_indicators, generate_signal


def _synthetic_ohlcv(n: int = 80, trend: float = 0.0, seed: int = 42) -> pd.DataFrame:
    """Build a deterministic OHLCV frame for tests.

    `trend` > 0 -> upward drift; < 0 -> downward; 0 -> flat-ish noise. The
    seed makes runs reproducible — the test would be useless if it flaked.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    base = 100 + np.cumsum(rng.standard_normal(n) + trend)
    return pd.DataFrame(
        {"Open": base, "High": base * 1.01, "Low": base * 0.99,
         "Close": base, "Volume": rng.integers(1_000_000, 5_000_000, n)},
        index=idx,
    )


def test_compute_indicators_adds_expected_columns():
    """compute_indicators must add every column the downstream task reads."""
    df = compute_indicators(_synthetic_ohlcv())
    expected = {"rsi", "macd", "macd_signal", "macd_hist",
                "bb_mid", "bb_upper", "bb_lower"}
    assert expected.issubset(df.columns), (
        f"missing columns: {expected - set(df.columns)}")


def test_generate_signal_returns_valid_shape():
    """The dict shape is the contract with Signal.objects.update_or_create."""
    result = generate_signal(_synthetic_ohlcv(), "TEST.NS")
    required = {"symbol", "date", "signal", "rsi", "macd", "macd_signal",
                "price", "reason"}
    assert required.issubset(result.keys())
    assert result["signal"] in {"BUY", "SELL", "HOLD"}
    assert isinstance(result["reason"], str) and result["reason"]


def test_insufficient_history_returns_safe_hold():
    """Less than 2 bars MUST NOT raise — return a HOLD with a clear reason."""
    one_bar = _synthetic_ohlcv(n=1)
    result = generate_signal(one_bar, "TEST.NS")
    assert result["signal"] == "HOLD"
    assert "insufficient" in result["reason"].lower()
    assert result["rsi"] is None  # nothing to compute on a single bar


def test_engine_records_rsi_extremes_in_reason():
    """When RSI is extreme, the reason text must mention it — even if the
    final signal is HOLD (because confluence needs >=2 of 3 votes).

    This locks in the *traceability* invariant: a reviewer reading
    Signal.reason should always see *why* the indicators voted as they did,
    not just the final BUY/SELL/HOLD label.
    """
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    # Sustained downtrend ending at the low — RSI will be deeply oversold.
    close = np.linspace(100, 60, n)
    df = pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": np.full(n, 1_000_000)},
        index=idx,
    )
    result = generate_signal(df, "TEST.NS")
    assert "rsi" in result["reason"].lower(), (
        f"RSI vote missing from reason text: {result['reason']!r}")
    # Also assert the RSI float landed in the structured fields, not just prose.
    assert result["rsi"] is not None and result["rsi"] < 35, (
        f"expected RSI < 35 on this downtrend, got {result['rsi']}")


def test_price_is_rounded_for_json_safety():
    """Price must be a JSON-safe float, not numpy.float64 with infinite digits."""
    result = generate_signal(_synthetic_ohlcv(), "TEST.NS")
    assert isinstance(result["price"], float)
    # round(x, 2) yields at most 2 decimal places.
    assert round(result["price"], 2) == result["price"]
