"""Database models for the `portfolio` app: Position, Order and JournalEntry.

Position/Order are populated in Week 4 when the broker / order manager is
wired up. JournalEntry is the agentic layer's audit trail — every decision the
analyst gate or the trading-session supervisor makes lands here.
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


class JournalEntry(models.Model):
    """One decision made by the agentic layer — the system's diary.

    WHY a journal table and not just log lines: logs answer "what happened"
    for a developer; the journal answers "why did the system trade (or refuse
    to)" for a *user* — queryable, renderable on the dashboard, and durable
    across restarts. An agent that can't explain its decisions afterwards is
    not auditable, and un-auditable agents don't ship in finance.

    INTERVIEW — agent observability: when asked how you'd monitor an
    autonomous trading agent, point here: every stage (signal, analyst
    verdict, execution, exit check, session summary) writes a structured row
    with a human-readable rationale plus a machine-readable payload.
    """

    STAGES = [
        ("signal", "Signal"),          # engine emitted / refreshed signals
        ("analyst", "Analyst"),        # LLM analyst verdict on a proposed trade
        ("execution", "Execution"),    # order routed to the broker
        ("exit", "Exit check"),        # stop-loss / take-profit decision
        ("session", "Session"),        # supervisor start / end / cycle summary
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    stage = models.CharField(max_length=12, choices=STAGES)
    # Blank for session-level entries that aren't about one stock.
    symbol = models.CharField(max_length=20, blank=True, default="")
    # Short decision word: APPROVE / VETO / REDUCE / SELL / HOLD / START / ...
    decision = models.CharField(max_length=20)
    # The human-readable rationale — the "why" a reviewer actually reads.
    detail = models.TextField(blank=True, default="")
    # Machine-readable context (verdict JSON, prices, counts) for the dashboard.
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        target = self.symbol or "session"
        return f"[{self.stage}] {target}: {self.decision}"
