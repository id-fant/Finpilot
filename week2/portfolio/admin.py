"""Django admin registration for the `portfolio` app."""
from django.contrib import admin

from .models import Order, Position


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
