"""FinPilot trading-session supervisor — the agentic market-hours loop.

WHY this exists: Celery Beat makes FinPilot *scheduled* (two fixed tasks per
day); this supervisor makes it *agentic* — a long-running process that stays
alive through market hours, re-evaluates the world every cycle, decides, acts
through the same production code path, and writes every decision to the
JournalEntry table so the whole session is auditable afterwards.

One cycle (repeated every --interval-minutes until close):

  1. Refresh signals        — signals.tasks.generate_daily_signals (production)
  2. Route orders           — portfolio.tasks.execute_signal_orders, which now
                              runs the week3 LLM analyst gate per trade and
                              books Position rows on fills
  3. Exit sweep             — mark every open Position to market; close any
                              that breach the stop-loss / take-profit bands
                              (an Order + Journal row records each exit)
  4. Journal a cycle summary

INTERVIEW — "what makes this agentic rather than a cron job?" The loop
OBSERVES (prices, news, book state), DECIDES among actions (trade / reduce /
veto / exit / hold) with an LLM advisory gate, ACTS through bounded tools
(OrderManager with hard risk caps), and EXPLAINS itself (journal). A cron job
only ever replays a fixed script.

Run (from project root):
    python scripts/run_trading_session.py                       # live data
    python scripts/run_trading_session.py --offline             # no network
    python scripts/run_trading_session.py --offline --force-open \
        --interval-minutes 0.05 --max-cycles 3                  # fast demo

Safety: paper broker by default (BROKER env var, same as the Celery path).
Ctrl+C at any point ends the session cleanly and prints the report.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, time as dtime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Project layout + Django setup (same pattern as run_integrated_demo.py) ──
ROOT = Path(__file__).resolve().parent.parent
WEEK2 = ROOT / "week2"
for p in (WEEK2, ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")
import django  # noqa: E402
django.setup()

from django.utils import timezone  # noqa: E402

# Force UTF-8 stdout/stderr — Windows cp1252 chokes on ₹ and box-drawing chars.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

from signals.tasks import generate_daily_signals      # noqa: E402
from portfolio.tasks import execute_signal_orders, _build_broker  # noqa: E402
from portfolio.models import JournalEntry, Order, Position  # noqa: E402

logger = logging.getLogger("supervisor")

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)


def now_ist() -> datetime:
    """Current time in Indian Standard Time — the market's clock, not the OS's."""
    return datetime.now(IST)


def market_is_open(at: datetime) -> bool:
    """NSE cash-market hours: Mon-Fri, 09:15-15:30 IST (holidays not modelled)."""
    return at.weekday() < 5 and MARKET_OPEN <= at.time() <= MARKET_CLOSE


def banner(title: str) -> None:
    print(f"\n{'═' * 78}\n  {title}\n{'═' * 78}")


# ── Offline mode ─────────────────────────────────────────────────────────────

def setup_offline(reset_db: bool) -> None:
    """Run the whole session against synthetic data — zero network.

    Reuses run_integrated_demo's synthetic panel + fetch monkeypatch, then
    REPLACES the static LTP stub with a drifting random walk so prices move
    between cycles — otherwise stop-loss / take-profit could never trigger
    and the exit path would go untested.

    Also blanks GEMINI_API_KEY for this process: offline means offline — the
    signal enricher and the analyst gate both short-circuit instantly instead
    of burning minutes in retry backoff against an unreachable API.

    WHY --reset-db matters offline: leftover rows (e.g. seed_demo positions at
    real-world prices) get marked against SYNTHETIC prices and instantly
    "hit their stop-loss" — a confusing artefact, not a real exit.
    """
    os.environ["GEMINI_API_KEY"] = ""
    import numpy as np
    import run_integrated_demo as demo  # noqa: PLC0415 - sibling script

    panel = demo.build_synthetic_panel()
    demo.install_synthetic_fetcher(panel)
    demo.reset_database(refresh_db=reset_db)

    from broker.paper_trade import PaperBroker
    rng = np.random.default_rng(7)
    state = {sym: float(df["Close"].iloc[-1]) for sym, df in panel.items()}

    # ±0.8%/call random walk around the last synthetic close. `self` unused —
    # the closure carries the state. pyrefly: ignore[unused-parameter]
    def _drifting_ltp(self, symbol: str) -> float:
        if symbol not in state:
            raise RuntimeError(f"no synthetic data for {symbol}")
        # float() pins numpy.float64 for the dict; pyrefly narrows early and
        # calls it redundant — same two-checker dance as strategy._clean().
        # pyrefly: ignore[unnecessary-type-conversion]
        state[symbol] *= 1 + float(rng.normal(0, 0.008))
        return round(state[symbol], 2)

    PaperBroker.get_ltp = _drifting_ltp
    print("  [offline] synthetic panel installed; LTP follows a seeded "
          "random walk so exits are exercisable")


# ── Exit sweep (cycle step 3) ────────────────────────────────────────────────

def sweep_positions(broker, *, stop_loss_pct: float, take_profit_pct: float,
                    when: date) -> dict:
    """Mark every open Position to market; close breaches of the exit bands.

    WHY the supervisor books exits directly (Position + Order rows) instead of
    routing a SELL through OrderManager: the paper broker's in-memory book is
    per-process and empty here, so it would reject the sell as a naked short.
    The DATABASE is FinPilot's book of record — for paper trading, recording
    the exit against it at the broker's quoted price IS the fill.
    """
    closed = held = errors = 0
    for pos in Position.objects.select_related("stock").filter(is_open=True):
        symbol = pos.stock.symbol
        try:
            ltp = broker.get_ltp(symbol)
        except Exception as e:  # noqa: BLE001 - one bad quote mustn't kill the sweep
            logger.warning("sweep: no LTP for %s (%s) — skipping", symbol, e)
            errors += 1
            continue

        avg = float(pos.avg_entry_price)
        move_pct = (ltp - avg) / avg * 100

        if move_pct <= -stop_loss_pct or move_pct >= take_profit_pct:
            rule = ("stop-loss" if move_pct < 0 else "take-profit")
            exit_price = Decimal(str(ltp))
            pos.pnl = ((exit_price - pos.avg_entry_price)
                       * pos.quantity).quantize(Decimal("0.01"))
            pos.is_open = False
            pos.exit_price = exit_price
            pos.exit_date = when
            pos.save()
            # The exit is a real (paper) trade — record it as an Order so the
            # dashboard's trade history tells the whole story.
            Order.objects.create(
                stock=pos.stock, signal=None, order_type="MARKET",
                side="SELL", quantity=pos.quantity, price=exit_price,
                status="COMPLETE", is_paper=True,
            )
            detail = (f"{rule} hit: {move_pct:+.2f}% vs entry "
                      f"₹{avg:.2f} → exit ₹{ltp:.2f}, "
                      f"P&L ₹{pos.pnl}")
            JournalEntry.objects.create(
                stage="exit", symbol=symbol, decision="SELL", detail=detail,
                payload={"rule": rule, "move_pct": round(move_pct, 2),
                         "entry": avg, "exit": ltp, "pnl": float(pos.pnl)},
            )
            print(f"    EXIT  {symbol:14s} {detail}")
            closed += 1
        else:
            # Live mark-to-market: pnl on an OPEN position = unrealised P&L,
            # so the dashboard's donut moves during the session.
            pos.pnl = (Decimal(str(ltp)) - pos.avg_entry_price) * pos.quantity
            pos.save(update_fields=["pnl"])
            held += 1

    return {"closed": closed, "held": held, "errors": errors}


# ── The session loop ─────────────────────────────────────────────────────────

def run_cycle(cycle: int, broker, args) -> dict:
    """One observe → decide → act → journal pass. Returns the cycle summary."""
    print(f"\n  ── cycle {cycle} @ {now_ist():%H:%M:%S IST} "
          f"{'─' * 40}")

    sig_summary = generate_daily_signals()
    print(f"    signals : {sig_summary['written']} written, "
          f"{len(sig_summary['failed'])} failed")

    order_summary = execute_signal_orders()
    print(f"    orders  : placed={order_summary['placed']} "
          f"skipped={order_summary['skipped']} "
          f"rejected={order_summary['rejected']} "
          f"vetoed={order_summary.get('vetoed', 0)}")

    exit_summary = sweep_positions(
        broker, stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct, when=date.today())
    print(f"    exits   : closed={exit_summary['closed']} "
          f"held={exit_summary['held']}")

    summary = {"cycle": cycle, "signals": sig_summary,
               "orders": order_summary, "exits": exit_summary}
    JournalEntry.objects.create(
        stage="session", decision="CYCLE",
        detail=(f"cycle {cycle}: {sig_summary['written']} signals, "
                f"{order_summary['placed']} orders placed, "
                f"{order_summary.get('vetoed', 0)} vetoed, "
                f"{exit_summary['closed']} exits, "
                f"{exit_summary['held']} positions held"),
        payload=summary,
    )
    return summary


def session_report(session_start: datetime) -> None:
    """The end-of-day diary — what the agent did and why, from the database.

    `session_start` must be timezone-AWARE (timezone.now()) — created_at rows
    are stored aware, and comparing them to a naive datetime raises Django's
    naive-datetime warning and can drift by the UTC offset.
    """
    banner("Session report")
    entries = list(JournalEntry.objects
                   .filter(created_at__gte=session_start)
                   .order_by("created_at"))
    cycles = [e for e in entries if e.decision == "CYCLE"]
    analyst = [e for e in entries if e.stage == "analyst"]
    exits = [e for e in entries if e.stage == "exit"]

    todays_orders = Order.objects.filter(created_at__gte=session_start)
    open_pos = list(Position.objects.select_related("stock").filter(is_open=True))
    open_pnl = sum(float(p.pnl) for p in open_pos)
    closed_today = Position.objects.filter(is_open=False,
                                           exit_date=date.today())
    realised = sum(float(p.pnl) for p in closed_today)

    print(f"  Cycles completed   : {len(cycles)}")
    print(f"  Orders this session: {todays_orders.count()} "
          f"({todays_orders.filter(status='COMPLETE').count()} filled)")
    print(f"  Analyst verdicts   : {len(analyst)} "
          f"({sum(1 for e in analyst if e.decision == 'VETO')} veto, "
          f"{sum(1 for e in analyst if e.decision == 'REDUCE')} reduce)")
    print(f"  Exits triggered    : {len(exits)}")
    print(f"  Realised P&L today : ₹{realised:,.2f}")
    print(f"  Open positions     : {len(open_pos)} "
          f"(unrealised ₹{open_pnl:,.2f})")
    for p in open_pos:
        print(f"    {p.stock.symbol:14s} x{p.quantity:<4d} "
              f"avg ₹{p.avg_entry_price}  P&L ₹{p.pnl}")

    if analyst or exits:
        print("\n  Decision diary (why, not just what):")
        for e in analyst + exits:
            # created_at is stored in UTC — print it on the market's clock.
            print(f"    [{e.created_at.astimezone(IST):%H:%M:%S}] {e.stage:7s} "
                  f"{e.symbol:14s} {e.decision:7s} {e.detail}")

    print("\n  Full audit trail: JournalEntry table "
          "(admin → Portfolio → Journal entries)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FinPilot market-hours trading supervisor")
    parser.add_argument("--interval-minutes", type=float, default=15.0,
                        help="minutes between cycles (default 15 — matches "
                             "yfinance's delayed-data granularity)")
    parser.add_argument("--offline", action="store_true",
                        help="synthetic data + random-walk LTPs, no network")
    parser.add_argument("--reset-db", action="store_true",
                        help="wipe Stock/Signal/Order/Position rows first for "
                             "a clean session (offline demos)")
    parser.add_argument("--max-cycles", type=int, default=None,
                        help="stop after N cycles (default: run to close)")
    parser.add_argument("--force-open", action="store_true",
                        help="ignore the market-hours check (for demos/tests)")
    parser.add_argument("--stop-loss-pct", type=float, default=2.0,
                        help="close a position when it falls this %% below "
                             "entry (default 2)")
    parser.add_argument("--take-profit-pct", type=float, default=4.0,
                        help="close a position when it rises this %% above "
                             "entry (default 4)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="[%(levelname)s] %(name)s: %(message)s")

    banner("FinPilot trading-session supervisor")
    from django.conf import settings

    # Offline setup FIRST — it blanks GEMINI_API_KEY, and the banner below
    # must report the gate state the session will actually run with.
    if args.offline:
        setup_offline(reset_db=args.reset_db)

    key_set = bool(os.environ.get("GEMINI_API_KEY"))
    print(f"  broker={settings.BROKER}  analyst_gate="
          f"{'on' if key_set and settings.ANALYST_GATE != 'off' else 'off'}"
          f"  interval={args.interval_minutes}m  "
          f"stop={args.stop_loss_pct}%  target={args.take_profit_pct}%"
          f"{'  [OFFLINE]' if args.offline else ''}")

    if not args.force_open and not market_is_open(now_ist()):
        print(f"\n  Market is closed (now {now_ist():%a %H:%M IST}; hours are "
              f"Mon-Fri {MARKET_OPEN:%H:%M}-{MARKET_CLOSE:%H:%M}).")
        print("  Re-run during market hours, or add --force-open for a demo.")
        return 1

    session_start = timezone.now()  # aware — matches auto_now_add rows
    broker = _build_broker()
    JournalEntry.objects.create(
        stage="session", decision="START",
        detail=(f"supervisor started — interval {args.interval_minutes}m, "
                f"stop {args.stop_loss_pct}%, target {args.take_profit_pct}%, "
                f"broker {settings.BROKER}"
                f"{', offline' if args.offline else ''}"),
    )

    cycle = 0
    try:
        while True:
            cycle += 1
            run_cycle(cycle, broker, args)

            if args.max_cycles is not None and cycle >= args.max_cycles:
                print(f"\n  max cycles ({args.max_cycles}) reached — ending session")
                break
            next_at = now_ist()
            if not args.force_open and next_at.time() >= MARKET_CLOSE:
                print("\n  market closed — ending session")
                break
            time.sleep(args.interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n  Ctrl+C — ending session cleanly")

    JournalEntry.objects.create(
        stage="session", decision="END",
        detail=f"supervisor stopped after {cycle} cycle(s)",
    )
    session_report(session_start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
