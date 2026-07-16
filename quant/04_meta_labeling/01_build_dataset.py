"""Meta-labeling step 1 — build the training dataset.

Runs the production confluence rules over ~5 years of the NIFTY 50 and emits
one row per BUY signal the engine would have fired, with:

  features — frozen strictly at signal time (core/ml_features.py — the SAME
             module the live gate uses, so training and serving can't drift)
  label    — did the trade clear Zerodha costs under the LIVE exit rules?
             Triple-barrier (López de Prado): entry at NEXT bar's open (no
             look-ahead), then whichever comes first of +4% target, -2% stop,
             or a 5-bar timeout — the supervisor's exact geometry.

WHY BUY signals only: the live system cannot short (OrderManager's
allow_short=False); SELL signals only ever close positions. Training on
short trades the system never takes would teach the model a distribution it
never sees.

WHY stop-priority on ambiguous bars: with daily OHLC we can't know whether
the High or the Low printed first inside a bar that touches both barriers.
Assuming the stop hit first is the conservative choice — it can only make
the training labels (and therefore the model) more pessimistic, never more
flattering.

KNOWN BIAS (disclosed, not hidden): the universe is TODAY's NIFTY 50
membership scanned backwards — survivorship bias. The stocks that crashed
out of the index are missing, so real-world performance is likely a bit
worse than the dataset suggests.

Run (from repo root):  python quant/04_meta_labeling/01_build_dataset.py
Output:                quant/04_meta_labeling/data/signals_dataset.csv
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pandas as pd

# core/ is framework-free but lives under week2/ — same sys.path bridge the
# integrated orchestrator uses.
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "week2"))

from core.costs import zerodha_round_trip_cost         # noqa: E402
from core.data import fetch_ohlcv                      # noqa: E402
from core.ml_features import (                          # noqa: E402
    FEATURES, HORIZON_BARS, STOP_PCT, TARGET_PCT,
    enrich_features, vectorized_votes,
)

OUT = Path(__file__).resolve().parent / "data" / "signals_dataset.csv"
PERIOD = "5y"
TRADE_VALUE = 50_000.0   # matches BROKER_MAX_TRADE_VALUE's default sizing
WARMUP_BARS = 200        # SMA-200 is the longest feature lookback

# Today's NIFTY 50 (survivorship caveat above). One bad ticker is skipped,
# never fatal — same resilience contract as core.data.fetch_universe.
NIFTY50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS",
    "BEL.NS", "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS",
    "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS",
    "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS", "INFY.NS", "ITC.NS",
    "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS", "M&M.NS", "MARUTI.NS",
    "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS",
    "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS", "SUNPHARMA.NS",
    "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
    "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS",
]


def label_trade(ind: pd.DataFrame, i: int) -> dict | None:
    """Triple-barrier outcome for a BUY signal on bar `i`.

    Entry at bar i+1's OPEN; barriers checked on bars i+1 .. i+HORIZON using
    High/Low (stop first on ambiguity); timeout exits at bar i+HORIZON's
    Close. Returns None when there aren't enough bars left to resolve.
    """
    if i + HORIZON_BARS >= len(ind):
        return None
    entry = float(ind["Open"].iloc[i + 1])
    if not math.isfinite(entry) or entry <= 0:
        return None
    stop = entry * (1 - STOP_PCT)
    target = entry * (1 + TARGET_PCT)

    exit_price, exit_rule = None, "timeout"
    for j in range(i + 1, i + 1 + HORIZON_BARS):
        low, high = float(ind["Low"].iloc[j]), float(ind["High"].iloc[j])
        if low <= stop:                      # conservative: stop checked first
            exit_price, exit_rule = stop, "stop"
            break
        if high >= target:
            exit_price, exit_rule = target, "target"
            break
    if exit_price is None:
        exit_price = float(ind["Close"].iloc[i + HORIZON_BARS])

    qty = math.floor(TRADE_VALUE / entry)
    if qty < 1:
        return None
    buy_value = qty * entry
    sell_value = qty * exit_price
    net = (sell_value - buy_value) - zerodha_round_trip_cost(buy_value, sell_value)
    return {
        "entry": round(entry, 2), "exit": round(exit_price, 2),
        "exit_rule": exit_rule,
        "net_rs": round(net, 2),
        "net_pct": round(net / buy_value * 100, 4),
        "label": int(net > 0),
    }


def scan_stock(symbol: str) -> list[dict]:
    """All labelled BUY-signal rows for one stock."""
    df = fetch_ohlcv(symbol, period=PERIOD)
    ind = vectorized_votes(enrich_features(df))
    rows: list[dict] = []
    buy_idx = [i for i, s in enumerate(ind["vec_signal"]) if s == "BUY"]
    for i in buy_idx:
        if i < WARMUP_BARS:
            continue  # feature lookbacks not warm yet — NaNs would leak in
        outcome = label_trade(ind, i)
        if outcome is None:
            continue
        # One dict literal (not .update calls) so the checkers infer a
        # str|float value type instead of pinning dict[str, str] on line one.
        rows.append({
            "symbol": symbol,
            "date": str(pd.Timestamp(ind.index[i]).date()),  # pyright: ignore[reportArgumentType]
            **{f: float(ind[f].iloc[i]) for f in FEATURES},
            **outcome,
        })
    return rows


def main() -> int:
    print(f"Scanning {len(NIFTY50)} stocks x {PERIOD} for BUY signals...")
    all_rows: list[dict] = []
    failed: list[str] = []
    t0 = time.time()
    for k, symbol in enumerate(NIFTY50, 1):
        try:
            rows = scan_stock(symbol)
            all_rows.extend(rows)
            print(f"  [{k:2d}/{len(NIFTY50)}] {symbol:16s} {len(rows):4d} signals")
        except Exception as e:  # noqa: BLE001 - one bad ticker never aborts the scan
            failed.append(symbol)
            print(f"  [{k:2d}/{len(NIFTY50)}] {symbol:16s} FAILED ({str(e)[:60]})")

    if not all_rows:
        print("No signals collected — aborting.")
        return 1

    data = pd.DataFrame(all_rows).sort_values("date").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT, index=False)

    took = time.time() - t0
    years = data["date"].str[:4]
    print(f"\nWrote {OUT} in {took:.0f}s")
    print(f"  rows          : {len(data)}  (stocks failed: {len(failed)})")
    print(f"  label balance : {data['label'].mean():.1%} profitable after costs")
    print(f"  avg net/trade : Rs.{data['net_rs'].mean():,.0f} on Rs.{TRADE_VALUE:,.0f}")
    print(f"  by exit rule  : {data['exit_rule'].value_counts().to_dict()}")
    print(f"  by year       : {years.value_counts().sort_index().to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
