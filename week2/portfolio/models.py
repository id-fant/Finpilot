"""Database models for the `portfolio` app: Position and Order.

These are populated in Week 4 when the broker / order manager is wired up. They
are defined now so the schema is stable and the API surface exists early.
"""
from django.db import models

from signals.models import Signal, Stock


class Position(models.Model):
    """A holding in one stock — currently open, or closed with realised P&L."""

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="positions",
    )
    quantity = models.IntegerField()
    avg_entry_price = models.DecimalField(max_digits=12, decimal_places=2)
    entry_date = models.DateField()
    is_open = models.BooleanField(default=True)
    exit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    exit_date = models.DateField(null=True, blank=True)
    # WHY default=0, not null: an open position has unrealised P&L of 0 so far,
    # which is a real value — not "unknown". Avoid nullable numeric fields when
    # 0 is the correct starting value; it removes a None-check everywhere.
    # `int 0` coerces to Decimal("0.00") at runtime; the suppression is a
    # django-types stub strictness — `default=Decimal("0")` would type-check
    # but generate a phantom migration diff, so we keep the idiomatic form.
    pnl = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # pyrefly: ignore[no-matching-overload]  # pyright: ignore[reportArgumentType]

    class Meta:
        ordering = ["-entry_date"]

    def __str__(self) -> str:
        state = "open" if self.is_open else "closed"
        return f"{self.stock.symbol} x{self.quantity} ({state})"


class Order(models.Model):
    """A single buy/sell order — paper by default, live once Week 4 wires Kite."""

    ORDER_TYPES = [("MARKET", "Market"), ("LIMIT", "Limit")]
    STATUSES = [
        ("PENDING", "Pending"), ("COMPLETE", "Complete"),
        ("CANCELLED", "Cancelled"), ("REJECTED", "Rejected"),
    ]

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="orders",
    )
    # WHY on_delete=SET_NULL here (vs CASCADE on `stock`): an order is a
    # historical fact — an audit record of something that happened. If the
    # source Signal is ever deleted, the order must SURVIVE, just with a null
    # link. CASCADE would wrongly erase trade history.
    signal = models.ForeignKey(
        Signal, on_delete=models.SET_NULL, null=True, blank=True,
    )
    order_type = models.CharField(max_length=10, choices=ORDER_TYPES)
    side = models.CharField(max_length=4)  # BUY / SELL
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUSES, default="PENDING")
    is_paper = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.side} {self.quantity} {self.stock.symbol} [{self.status}]"
