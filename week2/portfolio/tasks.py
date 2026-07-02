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

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


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
    from .models import Order

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
        return {"date": str(when), "placed": 0, "skipped": 0,
                "rejected": 0, "failed": 0, "total": 0}

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

    placed = skipped = rejected = failed = 0

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

    for signal in candidates:
        if (signal.pk, signal.signal_type) in existing_orders:
            logger.debug("execute_signal_orders: %s already has an order — skipping",
                         signal.stock.symbol)
            skipped += 1
            continue

        try:
            result = manager.execute_signal({
                "symbol": signal.stock.symbol,
                "action": signal.signal_type,
            })
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
            price=Decimal(str(result.get("price", signal.price))),
            status=("COMPLETE" if status == "COMPLETE"
                    else "PENDING" if status == "SUBMITTED"
                    else "REJECTED"),
            is_paper=is_paper,
        )

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
        "failed": failed,
        "total": len(candidates),
        "broker": settings.BROKER,
    }
    logger.info("execute_signal_orders: run complete — %s", summary)
    return summary
