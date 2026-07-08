"""URL routes for the research endpoints — mounted at /api/quant/.

Kept as a separate urls module (though the views live in the portfolio app)
so the mount prefix matches the repo's quant/ track by name.
"""
from django.urls import path

from .quant_views import (
    BacktestStatsView, MarkowitzWeightsView, MLModelView, PairsScanView,
)

urlpatterns = [
    path("pairs/", PairsScanView.as_view(), name="quant-pairs"),
    path("weights/", MarkowitzWeightsView.as_view(), name="quant-weights"),
    path("ml-model/", MLModelView.as_view(), name="quant-ml-model"),
    path("backtest-stats/", BacktestStatsView.as_view(), name="quant-backtest"),
]
