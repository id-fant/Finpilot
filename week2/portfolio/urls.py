"""URL routes for the `portfolio` app — mounted at /api/portfolio/."""
from django.urls import path

from .views import (
    JournalEntryListView, MonteCarloProjectionView, OrderHistoryView,
    PortfolioView,
)

urlpatterns = [
    path("", PortfolioView.as_view(), name="portfolio"),
    path("orders/", OrderHistoryView.as_view(), name="order-history"),
    # GET /api/portfolio/journal/?stage=...&symbol=... — agent decision diary.
    path("journal/", JournalEntryListView.as_view(), name="journal"),
    # GET /api/portfolio/projection/?symbol=...&capital=...&horizon_days=...
    # Returns percentile paths + summary stats for the dashboard fan chart.
    path("projection/", MonteCarloProjectionView.as_view(), name="mc-projection"),
]
