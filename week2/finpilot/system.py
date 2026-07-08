"""GET /api/system/ — the agent's control-room status.

One endpoint answering "what is FinPilot configured to do right now?":
broker mode, both decision gates (LLM analyst, ML meta-model), data state
(tracked stocks, latest signals, open book), and the live status of any
dashboard-launched background action.

Lives at project level (not in an app) because it aggregates across signals,
portfolio, week3 and week4 — no single app owns it.
"""
from __future__ import annotations

import logging
import os

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class SystemStatusView(APIView):
    """Read-only aggregate of configuration + pipeline state."""

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        from signals.models import Signal, Stock
        from portfolio.models import Order, Position
        from portfolio import runner

        # ── Gates ────────────────────────────────────────────────────────────
        gemini_key = bool(os.environ.get("GEMINI_API_KEY"))
        analyst_on = settings.ANALYST_GATE != "off" and gemini_key

        ml_info: dict = {"enabled": False}
        if settings.ML_GATE != "off":
            # core.ml_gate caches the artifact; this is cheap after first call.
            from core.ml_gate import _load, default_threshold
            loaded = _load()
            if loaded is not None:
                meta = loaded[1]
                ml_info = {
                    "enabled": True,
                    "threshold": settings.ML_GATE_THRESHOLD or default_threshold(),
                    "oos_auc": meta.get("oos_auc"),
                    "trained_at": meta.get("trained_at"),
                    "dataset_rows": meta.get("dataset_rows"),
                }

        # ── Data state ───────────────────────────────────────────────────────
        latest = Signal.objects.order_by("-date").values_list("date", flat=True).first()
        signals_latest = (Signal.objects.filter(date=latest).count()
                          if latest else 0)

        return Response({
            "broker": settings.BROKER,
            "debug": settings.DEBUG,
            "gates": {
                "analyst": {"enabled": analyst_on,
                            "mode": settings.ANALYST_GATE,
                            "gemini_key_set": gemini_key,
                            "model": os.environ.get("GEMINI_MODEL",
                                                    "gemini-flash-latest")},
                "ml": ml_info,
            },
            "data": {
                "tracked_stocks": Stock.objects.filter(is_tracked=True).count(),
                "latest_signal_date": latest,
                "signals_on_latest_date": signals_latest,
                "open_positions": Position.objects.filter(is_open=True).count(),
                "orders_total": Order.objects.count(),
            },
            "risk": {
                "max_trade_value": settings.BROKER_MAX_TRADE_VALUE,
                "max_positions": settings.BROKER_MAX_POSITIONS,
                "max_daily_orders": settings.BROKER_MAX_DAILY_ORDERS,
            },
            # Dashboard-launched background actions (portfolio/runner.py) —
            # the frontend polls this to flip buttons back to idle.
            "actions": runner.status(),
        })
