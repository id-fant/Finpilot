"""Persistence and reconciliation boundary for KiteTicker callbacks."""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import close_old_connections, transaction
from django.utils import timezone

from finpilot.events import publish_dashboard_event

logger = logging.getLogger(__name__)


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return timezone.make_aware(value) if timezone.is_naive(value) else value


def persist_ticks(ticks: list[dict[str, Any]],
                  token_to_stock_id: dict[int, int]) -> int:
    """Persist latest values and broadcast compact quote events."""
    from .models import MarketQuote

    close_old_connections()
    written = 0
    for tick in ticks:
        token = int(tick.get("instrument_token") or 0)
        stock_id = token_to_stock_id.get(token)
        last_price = tick.get("last_price")
        if not stock_id or last_price is None:
            continue
        quote, _ = MarketQuote.objects.select_related("stock").update_or_create(
            stock_id=stock_id,
            defaults={
                "instrument_token": token,
                "last_price": Decimal(str(last_price)),
                "exchange_timestamp": _aware(
                    tick.get("exchange_timestamp") or tick.get("timestamp")
                ),
            },
        )
        written += 1
        publish_dashboard_event("quote.updated", {
            "symbol": quote.stock.symbol,
            "last_price": str(quote.last_price),
            "exchange_timestamp": (
                quote.exchange_timestamp.isoformat()
                if quote.exchange_timestamp else None
            ),
        })
    return written


@transaction.atomic
def reconcile_order_update(update: dict[str, Any]) -> bool:
    """Apply a broker order update and its fill exactly once."""
    from .models import Order
    from .tasks import _apply_fill_to_position

    broker_id = str(update.get("order_id") or "")
    if not broker_id:
        return False
    order = (
        Order.objects.select_for_update()
        .select_related("stock")
        .filter(broker_order_id=broker_id)
        .first()
    )
    if order is None:
        logger.warning("Kite update for unknown order_id=%s", broker_id)
        return False

    broker_status = str(update.get("status") or "").upper()
    order.status = {
        "COMPLETE": "COMPLETE",
        "CANCELLED": "CANCELLED",
        "REJECTED": "REJECTED",
    }.get(broker_status, "PENDING")
    filled_quantity = int(update.get("filled_quantity") or order.quantity or 0)
    average_price = Decimal(str(
        update.get("average_price") or order.price or 0
    ))
    if filled_quantity:
        order.quantity = filled_quantity
    if average_price:
        order.price = average_price
    order.last_broker_update = timezone.now()

    if order.status == "COMPLETE" and not order.fill_applied:
        _apply_fill_to_position(
            order.stock, order.side, order.quantity, order.price, date.today(),
        )
        order.fill_applied = True

    order.save(update_fields=[
        "status", "quantity", "price", "fill_applied", "last_broker_update",
    ])
    transaction.on_commit(lambda: publish_dashboard_event("orders.updated", {
        "order_id": order.pk,
        "broker_order_id": broker_id,
        "status": order.status,
    }))
    return True
