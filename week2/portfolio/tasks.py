"""Celery tasks for the `portfolio` app.

This is the bridge between Week 2 (signals in the database) and Week 4 (a
broker that actually places orders). The daily flow is:

    09:05 IST  signals.generate_daily_signals  → writes today's BUY/SELL/HOLD
    09:20 IST  portfolio.execute_signal_orders → routes BUY/SELL through broker

The broker is chosen by the BROKER env var:
  paper  — PaperBroker (simulated money, FinPilot's safe default).
  kite   — KiteClient  (live Zerodha; requires KITE_ACCESS_TOKEN to be fresh).

INTERVIEW — "how do you go from paper to live trading?" PaperBroker and
KiteClient expose the SAME interface (get_ltp / place_order / get_positions).
OrderManager talks to whichever it is handed. The swap is one config flag,
no code change — ports-and-adapters in production.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

# Optional LLM analyst gate — week3's reviewer can veto or shrink a proposed
# trade before it reaches the broker. Guarded exactly like the enricher in
# signals/tasks.py: week2 works unchanged if week3 is absent or no key is set —
# the deterministic engine + OrderManager risk gates are the always-safe path.
review_trade: Any
analyst_headlines_for: Any
try:
    from llm.analyst import review_trade  # pyrefly: ignore[missing-import]
    from llm.news import headlines_for as analyst_headlines_for  # pyrefly: ignore[missing-import]
    _HAS_ANALYST = True
except ImportError:
    review_trade = None
    analyst_headlines_for = None
    _HAS_ANALYST = False


def _analyst_gate(signal, open_symbols: set[str]) -> dict | None:
    """Run the LLM analyst over one proposed trade. Returns a verdict or None.

    None means "gate not in play" — week3 missing, ANALYST_GATE=off, no
    GEMINI_API_KEY, or the LLM failed. The caller treats None as full-size
    approve: the gate FAILS OPEN. WHY fail-open and not fail-closed: the
    deterministic engine + OrderManager caps are the load-bearing safety
    rails; the analyst is an *extra* filter. Failing closed would mean an LLM
    outage silently halts all trading — an availability dependency an
    advisory component must never have.
    """
    import os
    if (not _HAS_ANALYST or settings.ANALYST_GATE == "off"
            or not os.environ.get("GEMINI_API_KEY")):
        return None
    sig_dict = {
        "symbol": signal.stock.symbol,
        "signal": signal.signal_type,
        "price": float(signal.price),
        "reason": signal.reason,
    }
    try:
        try:
            # pyrefly: ignore[not-callable] -- guarded by _HAS_ANALYST above
            headlines = analyst_headlines_for(signal.stock.symbol, limit=5)
        except Exception as e:  # noqa: BLE001 - news is best-effort
            logger.debug("analyst gate: headlines failed for %s: %s",
                         signal.stock.symbol, e)
            headlines = None
        # pyrefly: ignore[not-callable] -- guarded by _HAS_ANALYST above
        return review_trade(sig_dict, headlines=headlines,
                            portfolio={"open_symbols": sorted(open_symbols)})
    except Exception as e:  # noqa: BLE001 - LLM trouble must not block trading
        logger.warning("analyst gate failed for %s (%s) — failing open to "
                       "technical rules", signal.stock.symbol, e)
        return None


def _apply_fill_to_position(stock, side: str, quantity: int, price: Decimal,
                            when: date) -> None:
    """Upsert the Position row for one filled order — the broker's book,
    mirrored into the database the dashboard reads.

    BUY: create the open position, or fold the fill into the existing one at
    a volume-weighted average entry price (same maths as PaperBroker's
    `_add_position`). SELL: book realised P&L against the average entry and
    close the position when quantity reaches zero.

    WHY keyed on (stock, is_open=True): one open position per stock is this
    strategy's contract — signals are per-stock-per-day, and OrderManager
    blocks shorts. The unique key makes the upsert idempotent.
    """
    from .models import Position

    if quantity < 1:
        return
    open_pos = Position.objects.filter(stock=stock, is_open=True).first()

    if side == "BUY":
        if open_pos is None:
            Position.objects.create(
                stock=stock, quantity=quantity, avg_entry_price=price,
                entry_date=when,
            )
            logger.info("position: opened %s x%d @ %s", stock.symbol,
                        quantity, price)
        else:
            total_qty = open_pos.quantity + quantity
            invested = (open_pos.avg_entry_price * open_pos.quantity
                        + price * quantity)
            open_pos.avg_entry_price = (invested / total_qty).quantize(
                Decimal("0.01"))
            open_pos.quantity = total_qty
            open_pos.save(update_fields=["avg_entry_price", "quantity"])
            logger.info("position: added %s x%d — now x%d @ avg %s",
                        stock.symbol, quantity, total_qty,
                        open_pos.avg_entry_price)
        return

    # SELL — reduce or close.
    if open_pos is None:
        # The broker accepted a sell we have no book entry for (e.g. a live
        # holding bought outside FinPilot). Don't invent a phantom short row —
        # log it loudly; the Order row still records the trade itself.
        logger.warning("position: SELL fill for %s with no open position — "
                       "not tracked (held outside FinPilot?)", stock.symbol)
        return
    sold = min(quantity, open_pos.quantity)
    realised = ((price - open_pos.avg_entry_price) * sold).quantize(
        Decimal("0.01"))
    open_pos.pnl = open_pos.pnl + realised
    open_pos.quantity -= sold
    if open_pos.quantity <= 0:
        open_pos.is_open = False
        open_pos.exit_price = price
        open_pos.exit_date = when
    open_pos.save()
    logger.info("position: sold %s x%d @ %s — realised %s, %s",
                stock.symbol, sold, price, realised,
                "closed" if not open_pos.is_open else
                f"x{open_pos.quantity} still open")


def _build_broker():
    """Construct the broker object that today's run will use.

    Imports `broker` lazily (week4/ is on sys.path thanks to settings.py) so
    Celery autodiscover doesn't try to load kiteconnect at startup — useful in
    dev where the SDK isn't installed because you only paper-trade.
    """
    broker_kind = settings.BROKER
    if broker_kind == "kite":
        from broker import KiteClient
        logger.info("execute_signal_orders: using LIVE broker (Kite)")
        return KiteClient.from_env()
    if broker_kind == "paper":
        from broker import PaperBroker
        logger.info("execute_signal_orders: using paper broker "
                    "(starting cash %.0f)", settings.PAPER_STARTING_CASH)
        return PaperBroker(starting_cash=settings.PAPER_STARTING_CASH)
    raise ValueError(
        f"Unknown BROKER setting: {broker_kind!r}. Set BROKER=paper or kite.")


@shared_task(name="portfolio.execute_signal_orders")
def execute_signal_orders(target_date: str | None = None) -> dict:
    """Route today's BUY/SELL signals through the configured broker.

    Args:
        target_date: optional ISO date ("YYYY-MM-DD"). Defaults to today —
            override only for back-filling or testing a specific day.

    INTERVIEW — idempotency: signals are unique on (stock, date), and orders
    are deduped on (signal, side) inside the task. Re-running for the same date
    will NOT place a duplicate order for a signal that already has one — the
    same property generate_daily_signals relies on, applied one layer up.

    Returns:
        Summary dict — placed / skipped / rejected / failed counts.
    """
    # WHY import models INSIDE the function (not at module top): Celery
    # autodiscover loads tasks.py very early, before Django's app registry is
    # fully populated; a top-level model import can raise AppRegistryNotReady.
    # See LEARNINGS #44.
    from signals.models import Signal
    from .models import JournalEntry, Order, Position

    when = date.fromisoformat(target_date) if target_date else date.today()
    logger.info("execute_signal_orders: starting run for %s", when)

    # Pull only the actionable signals — HOLD generates no order, so filter it
    # at the DB level. select_related avoids the N+1 on signal.stock.symbol
    # (LEARNINGS #16). Evaluate once into a list so we count + iterate in one
    # query rather than calling .count() AND iterating.
    candidates = list(
        Signal.objects
        .filter(date=when, signal_type__in=["BUY", "SELL"])
        .select_related("stock")
    )
    logger.info("execute_signal_orders: %d actionable signal(s) for %s",
                len(candidates), when)

    if not candidates:
        return {"date": str(when), "placed": 0, "skipped": 0, "rejected": 0,
                "vetoed": 0, "ml_skipped": 0, "failed": 0, "total": 0}

    # WHY build OrderManager from settings.* (not hardcoded): the risk gates are
    # 12-factor config — adjustable per environment without a code change.
    from broker import OrderManager

    broker_obj = _build_broker()
    manager = OrderManager(
        broker_obj,
        max_trade_value=settings.BROKER_MAX_TRADE_VALUE,
        max_positions=settings.BROKER_MAX_POSITIONS,
        max_daily_orders=settings.BROKER_MAX_DAILY_ORDERS,
    )
    is_paper = settings.BROKER == "paper"

    placed = skipped = rejected = vetoed = ml_skipped = failed = 0

    # Resolve the ML gate threshold once: 0 = defer to the value chosen on
    # out-of-sample data at training time (core/ml_gate.py reads it from the
    # model's meta JSON).
    if settings.ML_GATE != "off":
        from core.ml_gate import default_threshold
        ml_threshold = settings.ML_GATE_THRESHOLD or default_threshold()
    else:
        ml_threshold = None

    # WHY one dedup query up front, not one .exists() per signal: re-running
    # the task for the same date must not double-fire orders — but checking
    # each signal individually costs N queries. Loading the already-ordered
    # (signal_id, side) pairs into a set costs ONE query and makes each check
    # a hash lookup. Same idempotency guarantee (LEARNINGS #48), N-1 fewer
    # round-trips.
    existing_orders = set(
        Order.objects
        .filter(signal__in=candidates)
        .values_list("signal_id", "side")
    )

    # Current book, for the analyst's portfolio context. Kept as a plain set of
    # symbols and updated in-loop so later signals in the same run see the
    # positions earlier fills just opened.
    open_symbols = set(
        Position.objects.filter(is_open=True)
        .values_list("stock__symbol", flat=True)
    )

    for signal in candidates:
        if (signal.pk, signal.signal_type) in existing_orders:
            logger.debug("execute_signal_orders: %s already has an order — skipping",
                         signal.stock.symbol)
            skipped += 1
            continue

        # ── Meta-labeling ML gate (quant/04, optional) ──────────────────────
        # First filter after dedup: the walk-forward model's P(clears costs).
        # Cheaper than the LLM gate (local inference, no metered API), so it
        # runs first — no point paying for an analyst verdict on a trade the
        # statistics already reject. NULL ml_prob = unscored -> passes through
        # (fail-open, same contract as the analyst gate).
        if (ml_threshold is not None and signal.signal_type == "BUY"
                and signal.ml_prob is not None
                and signal.ml_prob < ml_threshold):
            ml_skipped += 1
            # One journal row per skip per day — the supervisor re-runs this
            # task every cycle and must not spam duplicates (same dedup idea
            # as the VETO check below).
            if not JournalEntry.objects.filter(
                    stage="ml", symbol=signal.stock.symbol,
                    decision="SKIP", created_at__date=when).exists():
                JournalEntry.objects.create(
                    stage="ml", symbol=signal.stock.symbol, decision="SKIP",
                    detail=(f"meta-model P(clears costs)={signal.ml_prob:.2f} "
                            f"< threshold {ml_threshold:.2f} — trade skipped"),
                    payload={"ml_prob": signal.ml_prob,
                             "threshold": ml_threshold},
                )
            logger.info("execute_signal_orders: ML gate skipped %s "
                        "(p=%.2f < %.2f)", signal.stock.symbol,
                        signal.ml_prob, ml_threshold)
            continue

        # ── LLM analyst gate (week3, optional) ──────────────────────────────
        # The agentic step: an LLM reviews the proposed trade against fresh
        # headlines + the current book and can veto it or halve its size.
        # Every verdict is journalled — the agent must be auditable. The gate
        # fails OPEN (verdict None = proceed full size): OrderManager's
        # deterministic caps below remain the real safety rails.

        # A same-day VETO is final. A vetoed signal has no Order row, so the
        # dedup above can't catch it — without this check every supervisor
        # cycle would re-ask the LLM (a metered request) and write a
        # duplicate VETO journal row for the same trade.
        if JournalEntry.objects.filter(
                stage="analyst", symbol=signal.stock.symbol,
                decision="VETO", created_at__date=when).exists():
            logger.debug("execute_signal_orders: %s already vetoed today — "
                         "skipping", signal.stock.symbol)
            vetoed += 1
            continue

        budget = None
        verdict = _analyst_gate(signal, open_symbols)
        if verdict is not None:
            JournalEntry.objects.create(
                stage="analyst",
                symbol=signal.stock.symbol,
                decision=verdict["verdict"].upper(),
                detail=verdict["rationale"],
                payload=verdict,
            )
            if verdict["verdict"] == "veto":
                logger.warning("execute_signal_orders: analyst VETOED %s %s — %s",
                               signal.signal_type, signal.stock.symbol,
                               verdict["rationale"])
                vetoed += 1
                continue
            if verdict["verdict"] == "reduce":
                budget = settings.BROKER_MAX_TRADE_VALUE / 2
                logger.info("execute_signal_orders: analyst REDUCED %s to "
                            "half size — %s", signal.stock.symbol,
                            verdict["rationale"])

        try:
            result = manager.execute_signal({
                "symbol": signal.stock.symbol,
                "action": signal.signal_type,
            }, budget=budget)
        except Exception as exc:  # noqa: BLE001 - one bad ticker mustn't abort the batch
            logger.error("execute_signal_orders: FAILED for %s — %s",
                         signal.stock.symbol, exc, exc_info=True)
            failed += 1
            continue

        status = result.get("status", "REJECTED")

        # SKIPPED means OrderManager itself filtered it (e.g. a HOLD slipping
        # through, which our filter above should have prevented). Treat the
        # same as a real skip — nothing to persist.
        if status == "SKIPPED":
            skipped += 1
            continue

        # Persist every outcome — including rejections — as an Order row.
        # Rejected orders are audit material: "why didn't this signal trade?"
        # is a question you WILL be asked in any post-mortem.
        fill_price = Decimal(str(result.get("price", signal.price)))
        Order.objects.create(
            stock=signal.stock,
            signal=signal,
            order_type="MARKET",
            side=signal.signal_type,
            quantity=result.get("quantity", 0),
            # WHY Decimal: Order.price is a DecimalField (money). The broker
            # returns a float for the fill price — convert at the boundary so
            # the DB stores an exact value (LEARNINGS #45). Rejections without
            # a fill price get the signal price as a placeholder.
            price=fill_price,
            status=("COMPLETE" if status == "COMPLETE"
                    else "PENDING" if status == "SUBMITTED"
                    else "REJECTED"),
            is_paper=is_paper,
        )

        # ── Position bookkeeping (the fix for the dashboard's empty donut) ──
        # WHY COMPLETE only: a paper fill is always COMPLETE; a live Kite
        # order comes back SUBMITTED and is only *pending* — booking it as a
        # position before the exchange confirms would overstate the book.
        # (Live fill-confirmation polling is a later refinement.)
        if status == "COMPLETE":
            _apply_fill_to_position(
                signal.stock, signal.signal_type,
                result.get("quantity", 0), fill_price, when,
            )
            if signal.signal_type == "BUY":
                open_symbols.add(signal.stock.symbol)
            elif not Position.objects.filter(
                    stock=signal.stock, is_open=True).exists():
                open_symbols.discard(signal.stock.symbol)

        if status in ("COMPLETE", "SUBMITTED"):
            placed += 1
            logger.info("execute_signal_orders: %s %s %d @ %s [%s]",
                        signal.signal_type, signal.stock.symbol,
                        result.get("quantity", 0),
                        result.get("price", "?"), status)
        else:
            rejected += 1
            logger.warning("execute_signal_orders: REJECTED %s — %s",
                           signal.stock.symbol,
                           result.get("reason", "unknown"))

    summary = {
        "date": str(when),
        "placed": placed,
        "skipped": skipped,
        "rejected": rejected,
        "vetoed": vetoed,
        "ml_skipped": ml_skipped,
        "failed": failed,
        "total": len(candidates),
        "broker": settings.BROKER,
    }
    logger.info("execute_signal_orders: run complete — %s", summary)
    return summary
