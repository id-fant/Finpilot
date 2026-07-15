"""URL routes for the `portfolio` app — mounted at /api/portfolio/."""
from django.urls import path

from .views import (
    ExecuteOrdersView, JournalEntryListView, MonteCarloProjectionView,
    OrderHistoryView, PortfolioRiskView, PortfolioView,
)

urlpatterns = [
    path("", PortfolioView.as_view(), name="portfolio"),
    path("orders/", OrderHistoryView.as_view(), name="order-history"),
    # 1-day VaR/CVaR for the open book (historical simulation).
    path("risk/", PortfolioRiskView.as_view(), name="portfolio-risk"),
    # POST — dashboard "run now" action (202/409/403, see the view).
    path("execute-orders/", ExecuteOrdersView.as_view(), name="execute-orders"),
    # GET /api/portfolio/journal/?stage=...&symbol=... — agent decision diary.
    path("journal/", JournalEntryListView.as_view(), name="journal"),
    # GET /api/portfolio/projection/?symbol=...&capital=...&horizon_days=...
    # Returns percentile paths + summary stats for the dashboard fan chart.
    path("projection/", MonteCarloProjectionView.as_view(), name="mc-projection"),
]
