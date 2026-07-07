# 04 — Meta-labeling: an ML gate for the strategy's own signals

The "should FinPilot use ML?" answer, done the honest way. The model does
**not** predict prices — it predicts whether the confluence engine's own BUY
signals will clear Zerodha costs under the live exit rules (López de Prado's
*meta-labeling*). It deploys as one more gate in the order pipeline:

```
confluence rules → ML gate (this) → LLM analyst → OrderManager risk caps
```

## Run order

```bash
python quant/04_meta_labeling/01_build_dataset.py    # ~30s, live yfinance
python quant/04_meta_labeling/02_train_walkforward.py
python quant/04_meta_labeling/03_evaluate.py         # report PNG + tables
```

Artifacts land in `data/` and `model/` (both git-ignored — rebuild anytime).
Once `model/meta_model.joblib` exists, the live pipeline picks it up
automatically: `generate_daily_signals` scores every BUY into
`Signal.ml_prob`, and `execute_signal_orders` skips trades below the
threshold (journalled as `stage="ml"`). No model file → gate silently off.
Config: `ML_GATE=auto|off`, `ML_GATE_THRESHOLD` (0 = use the threshold
chosen on out-of-sample data at training time).

## Design decisions (interview material)

- **Meta-labeling, not price prediction** — "will MY signal make money" is a
  better-posed problem than "where will the price go", and it composes with
  the existing strategy instead of replacing it.
- **Triple-barrier labels matching the live exits** — entry at next bar's
  open, then first-touch of +4% target / −2% stop / 5-bar timeout, net of
  the Zerodha CNC cost stack. The label prices exactly the lifecycle the
  supervisor executes; stop-priority on ambiguous bars keeps labels
  conservative.
- **Walk-forward validation, never random splits** — expanding window by
  calendar year. Random splits leak the future and flatter the model.
- **Train/serve parity by construction** — features come from
  `week2/core/ml_features.py`, imported by BOTH the dataset builder and the
  live gate; a pytest (`test_ml_features.py`) asserts the vectorized scan
  agrees with the production engine bar-for-bar.
- **Fail-open deployment** — missing model, missing sklearn, NaN features:
  the gate returns None and the deterministic pipeline proceeds unchanged.

## Results (2026-07-08 training, 2022→2026 NIFTY 50)

| Metric | Value |
|---|---|
| Dataset | 1,230 BUY signals, 49/50 stocks, 5y |
| Base rate | 37.9% of trades clear costs |
| Unfiltered EV | −₹142 per ₹50k trade (OOS) |
| OOS AUC (walk-forward) | 0.529 |
| Filtered EV @ thr 0.5 | −₹78 per trade, 40% of trades kept |
| Top features | RSI depth, distance from 200-DMA |

**The honest conclusion:** the gate cuts the strategy's expected loss ~45%
by refusing the worst setups, but no threshold makes RSI mean-reversion
net-positive after costs — the edge is weak (AUC 0.53) and unstable across
years (the 2024 fold scored *below* chance). The two most important features
are the ones quant intuition predicts (oversold depth and the trend filter),
and on live synthetic BUYs the model's P≈0.22 agreed with an independent
bootstrap Monte Carlo's P(profit)≈21% — the model learned the cost floor,
not a money machine. That is exactly what a 20-line-per-day free data diet
buys, published without cherry-picking (see `meta_eval_report.png`).

**Known biases, disclosed:** survivorship (today's NIFTY-50 membership
scanned backwards), and daily-bar barrier ambiguity (resolved stop-first,
i.e. pessimistically).

Retrain quarterly, or whenever the strategy rules change:
steps 01 → 02 regenerate everything.
