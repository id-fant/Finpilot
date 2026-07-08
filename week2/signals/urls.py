"""URL routes for the `signals` app — mounted at /api/signals/ by finpilot/urls.py."""
from django.urls import path

from .views import (
    AskSignalView, ExplainSignalView, LatestSignalsView, NewsFeedView,
    RefreshSignalsView, SignalHistoryView, StockListView,
)

urlpatterns = [
    path("stocks/", StockListView.as_view(), name="stock-list"),
    path("latest/", LatestSignalsView.as_view(), name="latest-signals"),
    # Real market news (Yahoo + Zerodha Pulse) — before the <symbol> catch-all.
    path("news/", NewsFeedView.as_view(), name="news-feed"),
    # POST — dashboard "run now" action (202/409/403, see the view).
    path("refresh/", RefreshSignalsView.as_view(), name="signals-refresh"),
    # WHY these routes are LAST: Django matches patterns top-down. A bare
    # <symbol> would otherwise also match "stocks"/"latest"/"refresh" and
    # shadow them. Specific routes first, the catch-all parameter routes last.
    path("<str:symbol>/explain/", ExplainSignalView.as_view(), name="signal-explain"),
    path("<str:symbol>/ask/", AskSignalView.as_view(), name="signal-ask"),
    path("<str:symbol>/", SignalHistoryView.as_view(), name="signal-history"),
]
