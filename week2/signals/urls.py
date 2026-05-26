"""URL routes for the `signals` app — mounted at /api/signals/ by finpilot/urls.py."""
from django.urls import path

from .views import (
    ExplainSignalView, LatestSignalsView, SignalHistoryView, StockListView,
)

urlpatterns = [
    path("stocks/", StockListView.as_view(), name="stock-list"),
    path("latest/", LatestSignalsView.as_view(), name="latest-signals"),
    # WHY this route is LAST: Django matches patterns top-down. A bare
    # <symbol> would otherwise also match "stocks" and "latest" and shadow
    # them. Specific routes first, the catch-all parameter route last.
    path("<str:symbol>/explain/", ExplainSignalView.as_view(), name="signal-explain"),
    path("<str:symbol>/", SignalHistoryView.as_view(), name="signal-history"),
]
