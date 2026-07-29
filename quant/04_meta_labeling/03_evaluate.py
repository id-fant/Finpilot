"""Meta-labeling step 3 — evaluate the gate on honest out-of-sample data.

Everything here reads the OOF predictions written by 02_train_walkforward.py
— every row was predicted by a model that had never seen its year. No
in-sample flattery.

Prints the threshold-sweep table and renders a 3-panel report PNG:
  1. EV per trade vs gate threshold (diverging color: red loss / green gain)
  2. Fraction of trades the gate keeps vs threshold
  3. Permutation feature importance (from the meta json)

WHY 3 panels, not one chart with two y-axes: EV (rupees) and kept-fraction
(percent) are different measures — a dual-axis chart lets the eye invent
correlations that the arbitrary axis scaling created. Separate panels, one
scale each.

Run (from repo root):  python quant/04_meta_labeling/03_evaluate.py
Output:                quant/04_meta_labeling/meta_eval_report.png
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render-to-file; no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OOF = HERE / "data" / "oof_predictions.csv"
META = HERE / "model" / "meta_model_meta.json"
OUT_PNG = HERE / "meta_eval_report.png"

# Palette: blue for neutral magnitude (matches the dashboard's fan chart),
# muted red/green ONLY for the loss/gain polarity, gray for reference lines.
BLUE, RED, GREEN, GRAY, INK = "#2563EB", "#DC2626", "#16A34A", "#9CA3AF", "#374151"


def main() -> int:
    if not (OOF.exists() and META.exists()):
        raise SystemExit("run 02_train_walkforward.py first")
    oof = pd.read_csv(OOF)
    meta = json.loads(META.read_text(encoding="utf-8"))
    sweep = pd.DataFrame(meta["threshold_sweep"]).dropna()
    thr = meta["threshold"]

    # ── Console report ───────────────────────────────────────────────────────
    print(f"OOS rows {len(oof)} | AUC {meta['oos_auc']} | deploy threshold {thr}")
    print(f"unfiltered EV Rs.{meta['oos_ev_unfiltered_rs']}/trade -> "
          f"filtered Rs.{meta['oos_ev_filtered_rs']}/trade\n")
    dsr = meta.get("deflated_sharpe", {})
    pbo = meta.get("probability_backtest_overfitting", {})
    if dsr.get("probability") is not None:
        print(f"deflated-Sharpe confidence {dsr['probability']:.1%} | "
              f"CSCV backtest-overfitting probability "
              f"{pbo.get('probability', float('nan')):.1%}\n")
    print(sweep.to_string(index=False))
    print("\npermutation importance (last OOS year):")
    for f, v in sorted(meta["permutation_importance"].items(),
                       key=lambda kv: -kv[1]):
        print(f"  {f:14s} {v:+.4f}")

    # ── Report PNG ───────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    fig.suptitle("Meta-labeling gate — out-of-sample evaluation "
                 f"(walk-forward, {len(oof)} trades)", color=INK)

    thresholds = sweep["threshold"].to_numpy()
    evs = sweep["ev_per_trade_rs"].to_numpy(dtype=float)
    kept = sweep["kept_frac"].to_numpy(dtype=float) * 100

    # Panel 1 — EV per trade vs threshold. Polarity colored: loss red, gain
    # green; the unfiltered EV is the gray dashed baseline to beat.
    ax = axes[0]
    ax.bar(thresholds, evs, width=0.035,
           color=[GREEN if v >= 0 else RED for v in evs])
    ax.axhline(0, color=INK, linewidth=0.8)
    ax.axhline(meta["oos_ev_unfiltered_rs"], color=GRAY, linewidth=1,
               linestyle="--", label="unfiltered EV")
    ax.axvline(thr, color=BLUE, linewidth=1, linestyle=":",
               label=f"deployed thr={thr}")
    ax.set_xlabel("gate threshold  P(profit) ≥")
    ax.set_ylabel("EV per trade (₹)")
    ax.set_title("Expected value per kept trade")
    ax.legend(frameon=False, fontsize=8)

    # Panel 2 — how much strategy survives the gate.
    ax = axes[1]
    ax.plot(thresholds, kept, color=BLUE, linewidth=2, marker="o",
            markersize=4)
    ax.axvline(thr, color=BLUE, linewidth=1, linestyle=":")
    ax.set_xlabel("gate threshold  P(profit) ≥")
    ax.set_ylabel("trades kept (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Trade retention")

    # Panel 3 — permutation importance, sorted, single hue (magnitude job).
    ax = axes[2]
    imp = sorted(meta["permutation_importance"].items(), key=lambda kv: kv[1])
    names = [k for k, _ in imp]
    vals = np.array([v for _, v in imp])
    ax.barh(names, vals, height=0.55, color=BLUE)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_xlabel("permutation importance (AUC drop)")
    ax.set_title("What the model actually uses")

    for ax in axes:
        ax.grid(axis="y", color=GRAY, alpha=0.25, linewidth=0.5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors=INK, labelsize=8)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=130)
    print(f"\nreport chart -> {OUT_PNG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
