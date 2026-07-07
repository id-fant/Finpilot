"""Meta-labeling step 2 — walk-forward training.

Trains a HistGradientBoostingClassifier to predict P(signal clears costs)
and validates it the ONLY way that is honest for time series: expanding-
window walk-forward. Train on years 1..k, test on year k+1, roll forward.

WHY never a random split: signals from March 2024 in the train set and
February 2024 in the test set means the model has seen the future — the
classic leakage that makes toy projects report AUC 0.9 and lose money.

WHY HistGradientBoosting (sklearn) over LightGBM/XGBoost: identical model
family, already installed (zero new dependencies), and it tolerates NaN
features natively — which matters at serve time when a fresh listing has a
short history and dist_sma200 is NaN.

Outputs:
  model/meta_model.joblib   — final model, fit on ALL data after validation
  model/meta_model_meta.json — feature list, chosen threshold, fold metrics,
                               permutation importances (train/serve contract)
  data/oof_predictions.csv  — every out-of-sample prediction, for 03_evaluate

Run (from repo root):  python quant/04_meta_labeling/02_train_walkforward.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "week2"))
from core.ml_features import FEATURES  # noqa: E402

HERE = Path(__file__).resolve().parent
DATASET = HERE / "data" / "signals_dataset.csv"
OOF_OUT = HERE / "data" / "oof_predictions.csv"
MODEL_OUT = HERE / "model" / "meta_model.joblib"
META_OUT = HERE / "model" / "meta_model_meta.json"

# Keep at least a quarter of trades when picking the deployment threshold —
# a gate that vetoes 95% of signals has great stats and no strategy left.
MIN_KEEP_FRACTION = 0.25


def build_model() -> HistGradientBoostingClassifier:
    """One place to define hyper-parameters — small data, so keep the model
    modest; a deep ensemble would memorise 2k rows without blinking."""
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=15,
        min_samples_leaf=25, l2_regularization=1.0, random_state=42,
    )


def walk_forward(data: pd.DataFrame) -> pd.DataFrame:
    """Expanding-window folds by calendar year. Returns the OOF frame —
    every row of `data` that was ever predicted out-of-sample, with `prob`."""
    data = data.copy()
    data["year"] = data["date"].str[:4].astype(int)
    years = sorted(data["year"].unique())
    if len(years) < 3:
        raise SystemExit(f"need >=3 calendar years for walk-forward, got {years}")

    oof_parts: list[pd.DataFrame] = []
    print(f"{'fold':>6} {'train':>7} {'test':>6} {'base':>7} {'AUC':>6} "
          f"{'EV/all':>9} {'EV/p>=.5':>9}")
    for test_year in years[1:]:
        # pandas stubs union boolean-mask indexing as Series|DataFrame;
        # a mask on a DataFrame is always a DataFrame at runtime.
        train = cast("pd.DataFrame", data[data["year"] < test_year])  # pyrefly: ignore[redundant-cast]
        test = cast("pd.DataFrame", data[data["year"] == test_year])  # pyrefly: ignore[redundant-cast]
        train_label = cast("pd.Series", train["label"])  # pyrefly: ignore[redundant-cast]
        test_label = cast("pd.Series", test["label"])  # pyrefly: ignore[redundant-cast]
        # A fold needs both classes in train and enough test rows to mean much.
        if train_label.nunique() < 2 or len(test) < 20:
            print(f"{test_year:>6}  skipped (train classes={train_label.nunique()},"
                  f" test n={len(test)})")
            continue
        model = build_model()
        model.fit(train[FEATURES], train_label)
        probs = model.predict_proba(test[FEATURES])[:, 1]

        # list-of-columns selection is always a DataFrame at runtime; the
        # stubs union in Series (the duplicate-column paranoia).
        fold = cast("pd.DataFrame",  # pyrefly: ignore[redundant-cast]
                    test[["symbol", "date", "net_rs", "net_pct", "label"]]).copy()
        fold["prob"] = probs
        fold["fold"] = test_year
        oof_parts.append(fold)

        auc = roc_auc_score(test_label, probs) if test_label.nunique() > 1 else float("nan")
        kept = fold[fold["prob"] >= 0.5]
        print(f"{test_year:>6} {len(train):>7} {len(test):>6} "
              f"{test['label'].mean():>6.1%} {auc:>6.3f} "
              f"{test['net_rs'].mean():>9.0f} "
              f"{kept['net_rs'].mean() if len(kept) else float('nan'):>9.0f}")

    return pd.concat(oof_parts, ignore_index=True)


def pick_threshold(oof: pd.DataFrame) -> tuple[float, list[dict]]:
    """Sweep thresholds over the honest OOS predictions; pick the one that
    maximises EV per trade while keeping >= MIN_KEEP_FRACTION of trades."""
    sweep: list[dict] = []
    best_thr, best_ev = 0.5, -np.inf
    for thr in np.arange(0.30, 0.751, 0.05):
        kept = oof[oof["prob"] >= thr]
        frac = len(kept) / len(oof)
        ev = float(kept["net_rs"].mean()) if len(kept) else float("nan")
        sweep.append({"threshold": round(float(thr), 2),
                      "kept_frac": round(frac, 3),
                      "n": int(len(kept)),
                      "hit_rate": round(float(kept["label"].mean()), 3) if len(kept) else None,
                      "ev_per_trade_rs": round(ev, 1) if len(kept) else None})
        if frac >= MIN_KEEP_FRACTION and np.isfinite(ev) and ev > best_ev:
            best_thr, best_ev = round(float(thr), 2), ev
    return best_thr, sweep


def main() -> int:
    if not DATASET.exists():
        raise SystemExit(f"{DATASET} missing — run 01_build_dataset.py first")
    data = pd.read_csv(DATASET)
    print(f"dataset: {len(data)} BUY signals, "
          f"{data['label'].mean():.1%} profitable after costs\n")

    oof = walk_forward(data)
    OOF_OUT.parent.mkdir(parents=True, exist_ok=True)
    oof.to_csv(OOF_OUT, index=False)

    threshold, sweep = pick_threshold(oof)
    auc = roc_auc_score(oof["label"], oof["prob"])
    base_ev = float(oof["net_rs"].mean())
    kept = oof[oof["prob"] >= threshold]
    print(f"\nOOS overall: AUC {auc:.3f} | unfiltered EV Rs.{base_ev:.0f}/trade"
          f" | filtered@{threshold} EV Rs.{kept['net_rs'].mean():.0f}/trade "
          f"({len(kept)}/{len(oof)} kept)")

    # Final model: fit on everything. Validation already happened above —
    # shipping a model trained on less data than we have would be a waste.
    final = build_model()
    final.fit(data[FEATURES], data["label"])

    # Permutation importance on the LAST fold's test year (true OOS rows) —
    # impurity importances flatter high-cardinality features; permutation on
    # held-out data is the honest ranking.
    last_year = int(oof["fold"].max())
    hold = data[data["date"].str[:4].astype(int) == last_year]
    ref = build_model().fit(
        data[data["date"].str[:4].astype(int) < last_year][FEATURES],
        data[data["date"].str[:4].astype(int) < last_year]["label"])
    imp = permutation_importance(ref, hold[FEATURES], hold["label"],
                                 n_repeats=10, random_state=42)
    # Single-scorer call returns a Bunch (has importances_mean); the stubs
    # union in the multi-scorer dict-of-Bunch shape and lose the attribute.
    means = imp.importances_mean  # pyrefly: ignore[missing-attribute]  # pyright: ignore[reportAttributeAccessIssue]
    importances = {f: round(float(m), 4) for f, m in zip(FEATURES, means)}

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, MODEL_OUT)
    META_OUT.write_text(json.dumps({
        "features": FEATURES,
        "threshold": threshold,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_rows": len(data),
        "oos_auc": round(float(auc), 4),
        "oos_ev_unfiltered_rs": round(base_ev, 1),
        "oos_ev_filtered_rs": round(float(kept["net_rs"].mean()), 1),
        "threshold_sweep": sweep,
        "permutation_importance": importances,
    }, indent=2), encoding="utf-8")
    print(f"saved {MODEL_OUT.name} + {META_OUT.name} (threshold={threshold})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
