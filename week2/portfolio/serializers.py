"""DRF serializers for the `portfolio` app."""
from rest_framework import serializers

from .models import JournalEntry, MarketQuote, Order, Position


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
            "price", "status", "is_paper", "broker_order_id",
            "last_broker_update", "created_at",
        ]


class MarketQuoteSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", read_only=True)

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = MarketQuote
        fields = [
            "symbol", "instrument_token", "last_price",
            "exchange_timestamp", "received_at",
        ]


class JournalEntrySerializer(serializers.ModelSerializer):
    """One agent decision, exactly as the dashboard's Journal view renders it."""

    class Meta:  # pyrefly: ignore[bad-override]  # pyright: ignore[reportIncompatibleVariableOverride]
        model = JournalEntry
        fields = [
            "id", "created_at", "stage", "symbol", "decision", "detail",
            "payload",
        ]
