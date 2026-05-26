"""Django admin registration for the `signals` app.

A well-configured admin is free CRUD tooling — useful for seeding stocks and
eyeballing generated signals during development.
"""
from django.contrib import admin

from .models import Signal, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "sector", "is_tracked", "created_at")
    list_filter = ("is_tracked", "sector")
    search_fields = ("symbol", "name")


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ("stock", "date", "signal_type", "price", "rsi", "created_at")
    list_filter = ("signal_type", "date")
    search_fields = ("stock__symbol",)
    date_hierarchy = "date"
