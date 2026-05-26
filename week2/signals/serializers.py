"""DRF serializers for the `signals` app.

A serializer is the bridge between a model instance and JSON: it validates
incoming data and shapes outgoing data.
"""
from rest_framework import serializers

from .models import Signal, Stock


class StockSerializer(serializers.ModelSerializer):
    """Full representation of a Stock."""

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Stock
        fields = ["id", "symbol", "name", "sector", "is_tracked", "created_at"]


class SignalSerializer(serializers.ModelSerializer):
    """A Signal, with the parent stock's symbol and name flattened in.

    WHY the flattened fields: an API consumer wants the human-readable symbol,
    not just a numeric stock id. `source="stock.symbol"` follows the foreign key
    without a custom method. Pair this with `select_related("stock")` in the
    view so rendering N signals does not fire N extra queries (the N+1 problem).
    """

    symbol = serializers.CharField(source="stock.symbol", read_only=True)
    name = serializers.CharField(source="stock.name", read_only=True)

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Signal
        fields = [
            "id", "symbol", "name", "date", "signal_type", "price",
            "rsi", "macd", "macd_signal", "reason", "created_at",
        ]
