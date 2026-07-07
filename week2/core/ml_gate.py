"""The meta-labeling ML gate — framework-free scoring for live signals.

Loads the model trained by quant/04_meta_labeling/02_train_walkforward.py and
scores a BUY signal's probability of clearing costs under the live exit
rules. Sits in core/ because it is pure logic: no Django, no network — the
same ports-and-adapters contract as strategy.py.

Fallback contract (mirrors the LLM analyst gate): ANY missing piece — model
file absent, sklearn/joblib not installed, features unavailable — returns
None, and the caller treats None as "gate not in play". A missing model must
never block trading; the deterministic engine and OrderManager caps are the
load-bearing rails.

INTERVIEW — deployment parity: the features come from core/ml_features.py,
the SAME module the dataset builder used. The model artifact ships with a
meta JSON naming its feature list; scoring feeds exactly those names in
exactly that order. This is how you prevent train/serve skew without an
MLOps platform.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

from core.ml_features import enrich_features

logger = logging.getLogger(__name__)

# Default artifact location — override with ML_MODEL_PATH (e.g. in prod where
# the model is baked into the image at a different path).
_DEFAULT_MODEL = (Path(__file__).resolve().parent.parent.parent
                  / "quant" / "04_meta_labeling" / "model" / "meta_model.joblib")

# (model, meta) cache — loaded once per process, keyed on the resolved path
# so tests can repoint ML_MODEL_PATH without stale state.
_cache: dict[str, tuple[Any, dict] | None] = {}


def _model_path() -> Path:
    return Path(os.environ.get("ML_MODEL_PATH") or _DEFAULT_MODEL)


def _load() -> tuple[Any, dict] | None:
    """Load (model, meta) once; None if unavailable for any reason."""
    path = _model_path()
    key = str(path)
    if key in _cache:
        return _cache[key]

    result: tuple[Any, dict] | None = None
    meta_path = path.with_name("meta_model_meta.json")
    if path.exists() and meta_path.exists():
        try:
            import joblib  # deferred — sklearn stack is optional at runtime
            model = joblib.load(path)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            result = (model, meta)
            logger.info("ml_gate: loaded %s (trained %s, OOS AUC %s)",
                        path.name, meta.get("trained_at", "?"),
                        meta.get("oos_auc", "?"))
        except Exception as e:  # noqa: BLE001 - a bad artifact must not crash the task
            logger.warning("ml_gate: failed to load %s (%s) — gate disabled",
                           path, e)
    else:
        logger.debug("ml_gate: no model at %s — gate disabled", path)
    _cache[key] = result
    return result


def default_threshold(fallback: float = 0.5) -> float:
    """The threshold chosen on OOS data at training time (meta JSON)."""
    loaded = _load()
    return float(loaded[1].get("threshold", fallback)) if loaded else fallback


def score_signal(df: pd.DataFrame, buy_votes: int) -> float | None:
    """P(this BUY clears costs) for the LAST bar of an OHLCV frame.

    Args:
        df: the same OHLCV frame the strategy engine evaluated.
        buy_votes: confluence vote count from generate_signal's result.

    Returns:
        Probability in [0, 1], or None when the gate is not in play.
        NaN features (short history — e.g. dist_sma200 needs 200 bars) are
        passed through: HistGradientBoosting handles NaN natively.
    """
    loaded = _load()
    if loaded is None:
        return None
    model, meta = loaded
    try:
        ind = enrich_features(df)
        row = ind.iloc[-1]
        feats = {name: (float(buy_votes) if name == "buy_votes"
                        else float(row[name]) if pd.notna(row[name])
                        else float("nan"))
                 for name in meta["features"]}
        frame = pd.DataFrame([feats])[meta["features"]]
        return float(model.predict_proba(frame)[0, 1])
    except Exception as e:  # noqa: BLE001 - scoring trouble must not break the batch
        logger.warning("ml_gate: scoring failed (%s) — returning None", e)
        return None
