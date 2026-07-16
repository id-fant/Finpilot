"""Read-only research endpoints — the quant track, served over HTTP.

Mounted at /api/quant/ (see finpilot/urls.py). These wrap the SAME quant
scripts the CLI runs (loaded via importlib because their filenames start
with digits — the orchestrator's pattern), so the dashboard's Quant Lab and
`python quant/...` produce identical numbers by construction.

WHY the price-panel cache: the pairs scan and Markowitz weights both need
1y of OHLCV for every tracked stock — ~10-20s of sequential yfinance
fetches. Cached for an hour per symbol-set; daily bars don't move faster
than that.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.quant_loader import load_quant_module as _load_quant_module

logger = logging.getLogger(__name__)

PANEL_TTL = 3600.0  # seconds

# (symbols tuple) -> (fetched_at, {symbol: DataFrame})
_panel_cache: dict[tuple, tuple[float, dict[str, pd.DataFrame]]] = {}


def _tracked_panel() -> dict[str, pd.DataFrame]:
    """1y OHLCV per tracked stock, cached for PANEL_TTL."""
    from signals.models import Stock
    symbols = tuple(Stock.objects.filter(is_tracked=True)
                    .order_by("symbol").values_list("symbol", flat=True))
    if not symbols:
        raise RuntimeError("no tracked stocks — run manage.py seed_stocks")

    cached = _panel_cache.get(symbols)
    now = time.monotonic()
    if cached is not None and now - cached[0] < PANEL_TTL:
        return cached[1]

    from core.data import fetch_universe
    panel = fetch_universe(list(symbols), period="1y")
    if len(panel) < 2:
        raise RuntimeError(f"only {len(panel)} stock(s) fetched — need >=2")
    _panel_cache.clear()  # one panel in memory is plenty
    _panel_cache[symbols] = (now, panel)
    return panel


class PairsScanView(APIView):
    """GET /api/quant/pairs/ — Engle-Granger cointegration scan (quant/01).

    First call fetches the price panel (~10-20s); subsequent calls are
    instant for an hour. The dashboard shows a "computing…" state.
    """

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        try:
            panel = _tracked_panel()
            coint = _load_quant_module("01_mean_reversion/02_cointegration.py")
            prices = pd.DataFrame({s: df["Close"] for s, df in panel.items()})
            results = coint.scan_pairs(prices)
        except RuntimeError as e:
            return Response({"error": str(e)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        rows = [
            {"pair": r["pair"], "p_value": round(float(r["p_value"]), 4),
             "hedge_ratio": round(float(r["hedge_ratio"]), 3),
             "cointegrated": bool(r["cointegrated"])}
            for _, r in results.iterrows()
        ]
        logger.info("PairsScanView: %d pair(s), best p=%s",
                    len(rows), rows[0]["p_value"] if rows else "n/a")
        return Response({"pairs": rows, "period": "1y",
                         "universe": sorted(panel.keys())})


class MarkowitzWeightsView(APIView):
    """GET /api/quant/weights/ — max-Sharpe tangency weights (quant/03)."""

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        try:
            panel = _tracked_panel()
            sharpe = _load_quant_module(
                "03_portfolio_optimisation/02_sharpe_maximisation.py")
        except RuntimeError as e:
            return Response({"error": str(e)},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        returns = pd.DataFrame(
            {s: df["Close"].pct_change() for s, df in panel.items()}).dropna()
        mean = np.asarray(returns.mean()) * sharpe.TRADING_DAYS
        cov = np.asarray(returns.cov()) * sharpe.TRADING_DAYS
        weights = sharpe.max_sharpe_weights(mean, cov)
        # Sort the (symbol, weight) pairs BEFORE building dicts — sorting the
        # dicts by r["weight"] types as str|float and trips the checkers.
        ranked = sorted(zip(panel.keys(), weights), key=lambda kv: -float(kv[1]))
        out = [{"symbol": s, "weight": round(float(w), 4)} for s, w in ranked]
        logger.info("MarkowitzWeightsView: top %s @ %.1f%%",
                    out[0]["symbol"], out[0]["weight"] * 100)
        return Response({"weights": out, "period": "1y"})


class MLModelView(APIView):
    """GET /api/quant/ml-model/ — the meta-labeling model card (quant/04).

    Serves the training-time meta JSON (OOS AUC, threshold sweep, permutation
    importances) — the live counterpart of meta_eval_report.png.
    """

    META = (Path(settings.BASE_DIR).parent / "quant" / "04_meta_labeling"
            / "model" / "meta_model_meta.json")

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        if not self.META.exists():
            return Response(
                {"error": "no trained model — run quant/04_meta_labeling "
                          "scripts 01 then 02"},
                status=status.HTTP_404_NOT_FOUND)
        meta = json.loads(self.META.read_text(encoding="utf-8"))
        meta["gate_mode"] = settings.ML_GATE
        return Response(meta)


class BacktestStatsView(APIView):
    """GET /api/quant/backtest-stats/ — week1's results table, live.

    Same CSV (and same mtime-keyed cache) the Monte Carlo endpoint reads —
    the README results table, as JSON.
    """

    def get(self, request):  # pyrefly: ignore[unused-parameter]
        from .views import _load_backtest_stats
        table = _load_backtest_stats()
        if not table:
            return Response(
                {"error": "week1/nifty_comparison.csv missing — run "
                          "week1/01_data_foundations.py"},
                status=status.HTTP_404_NOT_FOUND)
        rows = [{"symbol": s, **vals} for s, vals in sorted(table.items())]
        return Response({"stats": rows, "source": "week1/nifty_comparison.csv"})
