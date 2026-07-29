"""One-query-contract bootstrap payload for the dashboard."""
from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolio.models import JournalEntry, MarketQuote, Order, Position
from portfolio.serializers import (
    JournalEntrySerializer, MarketQuoteSerializer, OrderSerializer,
    PositionSerializer,
)
from signals.models import Signal
from signals.serializers import SignalSerializer

from .system import system_payload


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DashboardSnapshotView(APIView):
    """Initial consistent snapshot; live events only invalidate this payload."""

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        latest = Signal.objects.order_by("-date").values_list("date", flat=True).first()
        signals = (
            Signal.objects.filter(date=latest).select_related("stock")
            if latest else Signal.objects.none()
        )
        positions = list(
            Position.objects.filter(is_open=True).select_related("stock")
        )
        total_pnl = Position.objects.aggregate(total=Sum("pnl"))["total"] or 0
        orders = Order.objects.select_related("stock").all()[:50]
        journal = JournalEntry.objects.all()[:50]
        quotes = MarketQuote.objects.select_related("stock").all()
        return Response({
            "snapshot_at": timezone.now(),
            "signals": SignalSerializer(signals, many=True).data,
            "positions": {
                "open_positions": PositionSerializer(positions, many=True).data,
                "open_count": len(positions),
                "total_pnl": total_pnl,
            },
            "orders": OrderSerializer(orders, many=True).data,
            "journal": JournalEntrySerializer(journal, many=True).data,
            "quotes": MarketQuoteSerializer(quotes, many=True).data,
            "system": system_payload(),
        })
