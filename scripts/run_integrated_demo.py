"""Full-pipeline FinPilot demo — exercises every architectural layer.

WHY this exists: `one_week_simulation.py` answers a narrow capital-floor
question using only summary stats from `nifty_comparison.csv`. This script
is the opposite — it pushes a single dataset through every layer of the
production code path AND the adjacent quant tools, then projects 1-week
outcomes for the resulting signals.

Layers exercised (in order):
  1. Synthetic OHLCV generation     — replaces yfinance for offline runs
  2. core.strategy.generate_signal  — week2 production signal engine
                                       (RSI + MACD + Bollinger confluence)
  3. signals.tasks.generate_daily_signals — Django task; writes Signals to DB
  4. portfolio.tasks.execute_signal_orders — paper broker routes orders
  5. quant pairs cointegration      — Engle-Granger test on the prices
  6. quant Markowitz optimisation   — tangency portfolio over the basket
  7. Monte Carlo over the signals   — projects the produced signals 1 week
  8. Consolidated report            — text + saved chart

Run (from project root):  python scripts/run_integrated_demo.py
                          python scripts/run_integrated_demo.py --refresh-db

What's NOT exercised:
  - Live yfinance fetch (sandbox blocks it; synthetic data is the substitute)
  - Live Gemini LLM calls (skipped unless GEMINI_API_KEY is set)
  - Cardinal React dashboard (visualisation — see `python run.py --demo`)
  - vectorbt parameter optimisation (week1/03_backtesting.py; separate concern)
  - FastAPI spike (separate process)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── Project layout ───────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
WEEK2 = ROOT / "week2"
QUANT = ROOT / "quant"

# Add week2/ to sys.path so `signals`, `portfolio`, `core` resolve.
for p in (WEEK2, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Django setup BEFORE importing models (same pattern as smoke_test.py).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")
import django  # noqa: E402
django.setup()

# Force UTF-8 stdout/stderr — Windows cp1252 chokes on ₹ and box-drawing chars.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# Now safe to import the production code path.
from signals.models import Stock, Signal              # noqa: E402
from portfolio.models import Order, Position         # noqa: E402
import signals.tasks                                  # noqa: E402  (monkeypatch target)
from signals.tasks import generate_daily_signals     # noqa: E402
from portfolio.tasks import execute_signal_orders    # noqa: E402


BASKET = [
    # (symbol, name, sector, daily_drift, daily_vol) — synthetic params per stock.
    # Drift varies so the engine produces a MIX of BUY/SELL/HOLD signals;
    # otherwise every stock votes the same way and the demo is unconvincing.
    ("RELIANCE.NS", "Reliance Industries", "Energy",     0.0008,  0.013),
    ("TCS.NS",      "Tata Consultancy",    "IT",        -0.0012,  0.016),
    ("HDFCBANK.NS", "HDFC Bank",           "Banking",    0.0005,  0.011),
    ("INFY.NS",     "Infosys",             "IT",        -0.0009,  0.018),
    ("ICICIBANK.NS","ICICI Bank",          "Banking",    0.0006,  0.012),
    ("SBIN.NS",     "State Bank of India", "Banking",    0.0007,  0.014),
]


def banner(title: str) -> None:
    """Section header — visual separator in the output."""
    print(f"\n{'═' * 78}")
    print(f"  {title}")
    print(f"{'═' * 78}")


# ── Layer 1: synthetic OHLCV ─────────────────────────────────────────────────
def build_synthetic_panel(n_days: int = 250, seed: int = 17) -> dict[str, pd.DataFrame]:
    """One OHLCV DataFrame per stock — deterministic via seed.

    Different drift/vol per stock produces signal variety. The series is long
    enough that RSI/MACD/Bollinger have full lookback windows.

    WHY anchor to today: `portfolio.tasks.execute_signal_orders` filters by
    today's date — if the synthetic series ends in the past, the broker sees
    zero actionable signals for "today" and routes nothing. Anchoring the
    last bar to today makes the full broker flow exercisable.
    """
    end = pd.Timestamp.today().normalize()
    idx = pd.bdate_range(end=end, periods=n_days)
    rng = np.random.default_rng(seed)
    panel: dict[str, pd.DataFrame] = {}

    # Inject a recent ~10-day downward shock on RELIANCE and SBIN so they
    # end the series in RSI-oversold territory (<35) and trigger BUY signals.
    # Without this every stock lands mid-range and we never exercise the
    # broker's order-fill path — only rejections — which is uninformative.
    SHOCK_STOCKS = {"RELIANCE.NS", "SBIN.NS"}
    SHOCK_DAYS = 10
    SHOCK_DAILY_DRIFT = -0.025  # -2.5%/day for the shock window

    for symbol, _, _, drift, vol in BASKET:
        # Geometric Brownian motion — the textbook synthetic price model.
        # log returns ~ N(drift, vol); prices = 100 * exp(cumsum(log_returns)).
        log_returns = rng.normal(drift, vol, n_days)
        if symbol in SHOCK_STOCKS:
            log_returns[-SHOCK_DAYS:] = rng.normal(SHOCK_DAILY_DRIFT, vol, SHOCK_DAYS)
        close = 100.0 * np.exp(np.cumsum(log_returns))
        # Add a small intraday spread so High/Low aren't degenerate.
        df = pd.DataFrame({
            "Open":   close * (1 + rng.normal(0, 0.001, n_days)),
            "High":   close * (1 + np.abs(rng.normal(0, 0.005, n_days))),
            "Low":    close * (1 - np.abs(rng.normal(0, 0.005, n_days))),
            "Close":  close,
            "Volume": rng.integers(500_000, 5_000_000, n_days).astype(float),
        }, index=idx)
        df.index.name = "Date"
        panel[symbol] = df
    return panel


def install_synthetic_fetcher(panel: dict[str, pd.DataFrame]) -> None:
    """Monkeypatch the two yfinance entry points the production path uses, so
    the whole flow runs offline against the synthetic panel:

      1. `signals.tasks.fetch_ohlcv` — feeds the engine with historical OHLCV.
      2. `PaperBroker.get_ltp` — fetches the last price when filling an order.

    Same monkeypatch pattern as `smoke_test.py`, extended to the broker side
    so order-fill works without network.
    """
    # `period` and `retries` mirror the real fetch_ohlcv signature so kwargs
    # from callers (`period="6mo"`) still bind — they're unused here.
    # pyrefly: ignore[unused-parameter]
    def _ohlcv_stub(symbol: str, period: str = "1y", retries: int = 3) -> pd.DataFrame:
        if symbol not in panel:
            raise RuntimeError(f"no synthetic data for {symbol}")
        return panel[symbol]
    signals.tasks.fetch_ohlcv = _ohlcv_stub

    # Last traded price = the last Close from the synthetic series.
    from broker.paper_trade import PaperBroker
    # `self` is required by the method protocol but unused here (closure
    # captures `panel`).
    # pyrefly: ignore[unused-parameter]
    def _ltp_stub(self, symbol: str) -> float:
        if symbol not in panel:
            raise RuntimeError(f"no synthetic data for {symbol}")
        return round(float(panel[symbol]["Close"].iloc[-1]), 2)
    PaperBroker.get_ltp = _ltp_stub


# ── Layer 2: seed stocks / clear prior demo state ────────────────────────────
def reset_database(refresh_db: bool) -> None:
    """Optionally wipe prior demo rows so each run starts clean."""
    if refresh_db:
        Order.objects.all().delete()
        Position.objects.all().delete()
        Signal.objects.all().delete()
        Stock.objects.all().delete()
        print("  [reset] cleared prior Stock/Signal/Order/Position rows")
    for symbol, name, sector, _, _ in BASKET:
        Stock.objects.get_or_create(symbol=symbol, defaults={"name": name, "sector": sector})


# ── Layer 5+6: quant tools (importlib because filenames start with digits) ──
def _load_quant_module(rel_path: str) -> Any:
    """Load `quant/.../NN_name.py` whose module name can't start with a digit."""
    full = QUANT / rel_path
    spec = importlib.util.spec_from_file_location(rel_path.replace("/", ".").replace(".py", ""), full)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {full}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_pairs_cointegration(panel: dict[str, pd.DataFrame]) -> dict:
    """Scan the basket for the most cointegrated pair (Engle-Granger)."""
    coint_mod = _load_quant_module("01_mean_reversion/02_cointegration.py")
    prices = pd.DataFrame({sym: df["Close"] for sym, df in panel.items()})
    results = coint_mod.scan_pairs(prices)
    top = results.iloc[0].to_dict()
    return {
        "pair": top["pair"],
        "p_value": top["p_value"],
        "hedge_ratio": top["hedge_ratio"],
        "cointegrated": bool(top["cointegrated"]),
    }


def run_markowitz_tangency(panel: dict[str, pd.DataFrame]) -> dict:
    """Compute the tangency (max-Sharpe) portfolio weights for the basket."""
    sharpe_mod = _load_quant_module("03_portfolio_optimisation/02_sharpe_maximisation.py")
    returns = pd.DataFrame({sym: df["Close"].pct_change() for sym, df in panel.items()}).dropna()
    mean = np.asarray(returns.mean()) * sharpe_mod.TRADING_DAYS
    cov = np.asarray(returns.cov()) * sharpe_mod.TRADING_DAYS
    weights = sharpe_mod.max_sharpe_weights(mean, cov)
    return {sym: float(round(w, 3)) for sym, w in zip(panel.keys(), weights)}


# ── Layer 7: Monte Carlo over the actual signals the engine emitted ─────────
def monte_carlo_on_signal(signal_row: Signal, panel: dict[str, pd.DataFrame],
                          capital: float = 1000.0, n_sims: int = 10_000) -> dict:
    """For one BUY/SELL signal, sample n_sims one-week outcomes from the
    stock's realised return distribution (NOT a fitted Normal — bootstrap).

    Bootstrapping from real returns captures fat tails the Normal misses.
    The cost stack is the same Zerodha CNC one from one_week_simulation.py."""
    symbol = signal_row.stock.symbol
    returns = panel[symbol]["Close"].pct_change().dropna()

    rng = np.random.default_rng(99)
    # Each sim: 5 daily returns sampled with replacement from history -> compound.
    # np.asarray pins the pandas-stub union (Categorical|ExtensionArray|ndarray)
    # down to ndarray so rng.choice's overload matches cleanly.
    history = np.asarray(returns.values, dtype=float)
    samples = rng.choice(history, size=(n_sims, 5))
    weekly_gross = np.prod(1 + samples, axis=1) - 1
    end_values = capital * (1 + weekly_gross)

    # Same Zerodha cost stack as one_week_simulation.py.
    costs = np.array([_round_trip_cost(capital, ev) for ev in end_values])
    net_end = end_values - costs
    net_pct = (net_end - capital) / capital * 100

    return {
        "symbol": symbol,
        "signal": signal_row.signal_type,
        "expected_net_pct": round(float(np.mean(net_pct)), 2),
        "p05_net_end": round(float(np.percentile(net_end, 5)), 2),
        "p50_net_end": round(float(np.percentile(net_end, 50)), 2),
        "p95_net_end": round(float(np.percentile(net_end, 95)), 2),
        "prob_profit_pct": round(float(np.mean(net_pct > 0)) * 100, 1),
    }


def _round_trip_cost(buy_value: float, sell_value: float) -> float:
    """Zerodha equity-delivery (CNC) round-trip — matches one_week_simulation.py."""
    stt = (buy_value + sell_value) * 0.001
    exch = (buy_value + sell_value) * 0.0000325
    sebi = (buy_value + sell_value) * 0.000001
    stamp = buy_value * 0.00015
    gst = (exch + sebi) * 0.18
    dp = 13.5 * 1.18
    return stt + exch + sebi + stamp + gst + dp


# ── Main orchestrator ────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--refresh-db", action="store_true",
                        help="wipe Stock/Signal/Order/Position rows before running")
    args = parser.parse_args()

    banner("FinPilot integrated demo — every layer, one run")
    print("  Synthetic OHLCV (250 trading days), 6-stock NSE basket, "
          "production code path.")

    # 1. Synthetic data + monkeypatch the production fetch.
    panel = build_synthetic_panel()
    install_synthetic_fetcher(panel)
    print(f"\n  [1] synthetic panel: {len(panel)} stocks × {len(next(iter(panel.values())))} days")

    # 2. Database state.
    reset_database(refresh_db=args.refresh_db)
    print(f"  [2] stocks in DB: {Stock.objects.count()}")

    # 3. Production signal engine via the Celery task.
    banner("Layer 3: signals.tasks.generate_daily_signals (production engine)")
    summary = generate_daily_signals()
    print(f"  result: {summary}")
    todays_signals = list(
        Signal.objects.select_related("stock").order_by("-date", "stock__symbol")[:len(BASKET)]
    )
    for sig in todays_signals:
        rsi = f"{sig.rsi:.1f}" if sig.rsi is not None else "  —"
        print(f"  {sig.stock.symbol:14s} {sig.date}  {sig.signal_type:4s}  "
              f"₹{sig.price:>8.2f}  rsi={rsi}")

    # 4. Paper broker.
    banner("Layer 4: portfolio.tasks.execute_signal_orders (paper broker)")
    order_summary = execute_signal_orders()
    print(f"  result: {order_summary}")
    recent_orders = list(Order.objects.select_related("stock").order_by("-created_at")[:10])
    for o in recent_orders:
        print(f"  {o.stock.symbol:14s} {o.side:4s}  x{o.quantity:>3d}  "
              f"@₹{o.price:>8.2f}  [{o.status}]")
    open_positions = list(Position.objects.select_related("stock").filter(is_open=True))
    print(f"  open positions: {len(open_positions)}")
    for p in open_positions:
        print(f"    {p.stock.symbol:14s} x{p.quantity}  avg ₹{p.avg_entry_price}  "
              f"P&L ₹{p.pnl}")

    # 5. Pairs cointegration (quant tool).
    banner("Layer 5: quant pairs cointegration (Engle-Granger on the panel)")
    pair = run_pairs_cointegration(panel)
    print(f"  most cointegrated pair : {pair['pair']}")
    print(f"  p-value                : {pair['p_value']:.4f}")
    print(f"  hedge ratio            : {pair['hedge_ratio']:.3f}")
    print(f"  cointegrated (p<0.05)  : {pair['cointegrated']}")

    # 6. Markowitz tangency portfolio.
    banner("Layer 6: quant Markowitz max-Sharpe weights (tangency portfolio)")
    weights = run_markowitz_tangency(panel)
    for sym, w in sorted(weights.items(), key=lambda x: -x[1]):
        bar = "█" * int(w * 50)
        print(f"  {sym:14s}  {w:>6.1%}  {bar}")

    # 7. Monte Carlo for every BUY/SELL signal the engine produced.
    banner("Layer 7: 1-week Monte Carlo per signal (₹1,000 each, bootstrap n=10k)")
    actionable = [s for s in todays_signals if s.signal_type in {"BUY", "SELL"}]
    if not actionable:
        print("  [skip] no actionable BUY/SELL signals — every stock voted HOLD.")
        mc_results = []
    else:
        print(f"  {'Stock':14s}{'Signal':>8s}{'Exp net %':>11s}{'P50 end':>11s}"
              f"{'P05 end':>11s}{'P95 end':>11s}{'P(profit)':>11s}")
        print(f"  {'-' * 74}")
        mc_results = [monte_carlo_on_signal(s, panel) for s in actionable]
        for r in mc_results:
            print(f"  {r['symbol']:14s}{r['signal']:>8s}"
                  f"{r['expected_net_pct']:>10.2f}%"
                  f"{r['p50_net_end']:>11.2f}"
                  f"{r['p05_net_end']:>11.2f}"
                  f"{r['p95_net_end']:>11.2f}"
                  f"{r['prob_profit_pct']:>10.1f}%")

    # 8. Consolidated takeaways.
    banner("Final report")
    n_buy = sum(1 for s in todays_signals if s.signal_type == "BUY")
    n_sell = sum(1 for s in todays_signals if s.signal_type == "SELL")
    n_hold = sum(1 for s in todays_signals if s.signal_type == "HOLD")
    print(f"  Signal mix             : {n_buy} BUY · {n_sell} SELL · {n_hold} HOLD")
    print(f"  Orders placed (paper)  : {order_summary.get('placed', 0)}")
    print(f"  Open positions         : {len(open_positions)}")
    print(f"  Best cointegrated pair : {pair['pair']} (p={pair['p_value']:.4f})")
    top_weight = max(weights.items(), key=lambda x: x[1])
    print(f"  Top Markowitz weight   : {top_weight[0]} @ {top_weight[1]:.1%}")
    if mc_results:
        avg_expected = sum(r["expected_net_pct"] for r in mc_results) / len(mc_results)
        print(f"  Avg 1-wk expected net  : {avg_expected:.2f}% (₹1,000 per signal)")
        prob_winner = sum(1 for r in mc_results if r["expected_net_pct"] > 0)
        print(f"  Net-profitable signals : {prob_winner}/{len(mc_results)} "
              f"(after Zerodha costs)")

    print(f"\n  Layers exercised: synthetic OHLCV -> signal engine -> Django ORM ->")
    print(f"                    paper broker -> cointegration -> Markowitz -> Monte Carlo")
    print(f"  Skipped: live yfinance (sandbox), live Gemini (no key), dashboard render")
    return 0


if __name__ == "__main__":
    sys.exit(main())
