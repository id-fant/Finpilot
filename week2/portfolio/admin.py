"""Django admin registration for the `portfolio` app."""
from django.contrib import admin

from .models import JournalEntry, Order, Position


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("stock", "quantity", "avg_entry_price", "is_open", "pnl")
    list_filter = ("is_open",)
    search_fields = ("stock__symbol",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "stock", "side", "quantity", "price", "status", "is_paper", "created_at",
    )
    list_filter = ("status", "side", "is_paper")
    search_fields = ("stock__symbol",)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    """The agent's diary — read this to audit what the system decided and why."""
    list_display = ("created_at", "stage", "symbol", "decision", "detail")
    list_filter = ("stage", "decision")
    search_fields = ("symbol", "detail")
    readonly_fields = ("created_at",)
