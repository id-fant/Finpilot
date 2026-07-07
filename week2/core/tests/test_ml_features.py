"""Tests for the meta-labeling feature layer and the ML gate's fallback.

The agreement test is the load-bearing one: core/ml_features.py re-implements
the confluence rules in vectorized form for the 5-year dataset scan, while
core/strategy.py evaluates only the last bar. If the two ever disagree, the
model trains on signals the live engine would never fire — silent train/serve
skew. This test makes that drift loud.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.ml_features import FEATURES, enrich_features, vectorized_votes
from core.strategy import generate_signal


def _synthetic_ohlcv(n: int = 300, seed: int = 7) -> pd.DataFrame:
    """Volatile synthetic OHLCV — enough variance that all three vote rules
    (RSI extremes, MACD crossovers, Bollinger breaches) actually fire."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    # Regime-switching drift so RSI visits both extremes over the sample.
    drift = np.repeat(rng.normal(0, 0.004, n // 25 + 1), 25)[:n]
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, n) + drift))
    return pd.DataFrame(
        {"Open": close * (1 + rng.normal(0, 0.002, n)),
         "High": close * (1 + np.abs(rng.normal(0, 0.006, n))),
         "Low": close * (1 - np.abs(rng.normal(0, 0.006, n))),
         "Close": close,
         "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float)},
        index=idx,
    )


def test_vectorized_scan_agrees_with_production_engine():
    """For many random cut-points, the vectorized per-bar signal must equal
    what generate_signal says when handed the frame truncated at that bar."""
    df = _synthetic_ohlcv()
    vec = vectorized_votes(enrich_features(df))

    rng = np.random.default_rng(0)
    # 40 random evaluation points past the indicator warm-up window.
    for i in sorted(rng.choice(np.arange(40, len(df)), size=40, replace=False)):
        expected = generate_signal(df.iloc[: i + 1], "TEST.NS")
        got = vec["vec_signal"].iloc[i]
        assert got == expected["signal"], (
            f"bar {i} ({pd.Timestamp(df.index[i]).date()}): vectorized={got!r} "  # pyright: ignore[reportArgumentType]
            f"engine={expected['signal']!r} — the scan and the engine drifted")
        assert int(vec["buy_votes"].iloc[i]) == expected["buy_votes"]
        assert int(vec["sell_votes"].iloc[i]) == expected["sell_votes"]


def test_enrich_features_produces_all_model_features():
    """Every name the trained model expects must exist (buy_votes comes from
    vectorized_votes / the engine result, not enrich_features)."""
    ind = vectorized_votes(enrich_features(_synthetic_ohlcv()))
    missing = [f for f in FEATURES if f not in ind.columns]
    assert not missing, f"feature columns missing: {missing}"
    # Past the 200-bar warm-up, features must be finite (no silent all-NaN).
    tail = ind.iloc[250:][FEATURES]
    assert tail.notna().all().all(), (
        f"NaNs past warm-up in: {tail.columns[tail.isna().any()].tolist()}")


def test_ml_gate_fails_open_without_model(monkeypatch):
    """No model artifact -> score_signal returns None (gate not in play).
    The trading pipeline must keep working on a machine that never ran
    quant/04 training — same fail-open contract as the LLM analyst gate."""
    from core import ml_gate
    monkeypatch.setenv("ML_MODEL_PATH", r"C:\nonexistent\meta_model.joblib")
    ml_gate._cache.clear()  # bust the per-path memo for this test
    assert ml_gate.score_signal(_synthetic_ohlcv(), buy_votes=2) is None
    assert ml_gate.default_threshold(0.5) == 0.5
