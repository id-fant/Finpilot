"""DRF serializers for the `portfolio` app."""
from rest_framework import serializers

from .models import Order, Position


class PositionSerializer(serializers.ModelSerializer):
    """A Position with the stock symbol flattened in for readability."""

    symbol = serializers.CharField(source="stock.symbol", read_only=True)

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Position
        fields = [
            "id", "symbol", "quantity", "avg_entry_price", "entry_date",
            "is_open", "exit_price", "exit_date", "pnl",
        ]


class OrderSerializer(serializers.ModelSerializer):
    """An Order with the stock symbol flattened in for readability."""

    symbol = serializers.CharField(source="stock.symbol", read_only=True)

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = Order
        fields = [
            "id", "symbol", "signal", "order_type", "side", "quantity",
            "price", "status", "is_paper", "created_at",
        ]
