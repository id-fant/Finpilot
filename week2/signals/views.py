"""Read-only API views for the `signals` app.

WHY generic ListAPIView: these endpoints are pure reads. DRF's generic views
give pagination, content negotiation and the browsable API for free — a custom
view would just re-implement all of that.

Each view logs what it returned (and warns on empty / unknown-symbol cases), so
an "API returned nothing" report can be traced from the logs without a debugger.
"""
import logging

from django.core.cache import cache
from django.db.models import QuerySet
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Signal, Stock
from .serializers import SignalSerializer, StockSerializer

logger = logging.getLogger(__name__)


class StockListView(generics.ListAPIView):
    """GET /api/signals/stocks/ — every stock under coverage."""

    serializer_class = StockSerializer

    # WHY the annotation + the suppression: DRF's stub declares
    # `GenericAPIView.get_queryset(self) -> QuerySet[_MT_co]` BUT doesn't make
    # GenericAPIView itself `Generic[_MT_co]` — so a concrete `QuerySet[Stock]`
    # can't unify with the floating type variable, and Pyrefly's strict variance
    # check rejects the override. Pyright (and the runtime) handle it correctly.
    # `# pyrefly: ignore[bad-override]` documents that this is a stub limitation,
    # not a real bug — re-evaluate if djangorestframework-types fixes the generic.
    def get_queryset(self) -> QuerySet[Stock]:  # pyrefly: ignore[bad-override]
        qs = Stock.objects.all()
        logger.info("StockListView: returning %d stock(s)", qs.count())
        return qs


class LatestSignalsView(generics.ListAPIView):
    """GET /api/signals/latest/ — the signals from the most recent run."""

    serializer_class = SignalSerializer

    def get_queryset(self) -> QuerySet[Signal]:  # pyrefly: ignore[bad-override]
        # WHY this approach: the ideal query is DISTINCT ON (stock) ordered by
        # date, but SQLite (the dev DB) has no DISTINCT ON. Instead we find the
        # newest date present, then return that day's signals. select_related
        # joins the Stock in one query, avoiding an N+1 when serialising.
        latest_date = (
            Signal.objects.order_by("-date")
            .values_list("date", flat=True)
            .first()
        )
        if latest_date is None:
            # WARNING, not silent: an empty /latest/ almost always means the
            # daily task has not run yet — say so in the logs.
            logger.warning("LatestSignalsView: no signals in the database — "
                            "has generate_daily_signals run?")
            return Signal.objects.none()

        qs = Signal.objects.filter(date=latest_date).select_related("stock")
        logger.info("LatestSignalsView: %d signal(s) for latest date %s",
                    qs.count(), latest_date)
        return qs


class SignalHistoryView(generics.ListAPIView):
    """GET /api/signals/<symbol>/ — full signal history for one stock."""

    serializer_class = SignalSerializer

    def get_queryset(self) -> QuerySet[Signal]:  # pyrefly: ignore[bad-override]
        symbol = self.kwargs["symbol"]
        qs = (
            Signal.objects.filter(stock__symbol=symbol)
            .select_related("stock")
        )
        count = qs.count()
        if count == 0:
            # WARNING: distinguishes "unknown ticker" / "no signals yet" from a
            # real error — a common source of confused "why is it empty?" reports.
            logger.warning("SignalHistoryView: no signals for symbol '%s' — "
                            "unknown ticker, or none generated for it yet", symbol)
        else:
            logger.info("SignalHistoryView: %d signal(s) for %s", count, symbol)
        return qs


class ExplainSignalView(APIView):
    """GET /api/signals/<symbol>/explain/ — LLM-generated explanation of the latest signal.

    On first call for a given (symbol, date) the Week 3 LLM explainer
    (`llm.explainer.explain_signal`) is invoked. The result is cached for 24h
    so a second call costs nothing. Pass `?refresh=1` to bypass the cache.

    The symbol can be passed bare ("RELIANCE") or NSE-suffixed ("RELIANCE.NS") —
    the lookup tries both, so the Cardinal frontend (which uses bare symbols)
    works without an extra translation step.

    Returns:
      200 — { symbol, date, signal_type, price, rsi, macd, technical_reason,
              explanation, cached }
      404 — no signal exists for that symbol
      502 — LLM call failed (no API key, rate-limit after retries, etc.)
      503 — Week 3 LLM package not installed
    """

    CACHE_TTL = 60 * 60 * 24  # 24 hours

    def get(self, request, symbol):
        # 1. Lookup — accept bare ("RELIANCE") or suffixed ("RELIANCE.NS").
        signal = (
            Signal.objects
            .filter(stock__symbol__in=[symbol, f"{symbol}.NS"])
            .select_related("stock")
            .order_by("-date")
            .first()
        )
        if signal is None:
            logger.warning("ExplainSignalView: no signal for '%s'", symbol)
            return Response(
                {"error": f"no signal found for '{symbol}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 2. Cache check — key on signal.pk since one row per (stock, date).
        cache_key = f"signal:explain:{signal.pk}"
        refresh = request.query_params.get("refresh") == "1"
        cached = None if refresh else cache.get(cache_key)
        if cached:
            logger.info("ExplainSignalView: cache hit for %s (%s)",
                        signal.stock.symbol, signal.date)
            return Response(self._payload(signal, cached, was_cached=True))

        # 3. Lazy imports — only this endpoint fails if Week 3 isn't installed,
        # not all of Django.
        try:
            from llm.explainer import explain_signal as _explain
            from llm.news import headlines_for
        except ImportError as e:
            logger.error("ExplainSignalView: LLM unavailable — %s", e)
            return Response(
                {"error": "LLM layer not installed. Run: "
                          "pip install -r week3/requirements.txt"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 4. Build the dict the explainer expects. WHY a dict and not the model:
        # keeps llm/ Django-free (ports-and-adapters — the model is an adapter).
        signal_dict = {
            "symbol": signal.stock.symbol,
            "signal": signal.signal_type,
            "price": float(signal.price),
            "rsi": signal.rsi,
            "macd": signal.macd,
            "macd_signal": signal.macd_signal,
            "reason": signal.reason,
        }

        # 5. Fetch recent headlines for news-sentiment context (step 1.5).
        # Best-effort: if the news sources are down or rate-limited, we still
        # generate an explanation from technicals alone — `headlines_for` never
        # raises, but we wrap the call defensively in case that contract slips.
        headlines: list[str] = []
        try:
            headlines = headlines_for(signal.stock.symbol, limit=10)
        except Exception as e:  # noqa: BLE001 - news must never kill the explain
            logger.warning("ExplainSignalView: headlines unavailable for %s — %s",
                           signal.stock.symbol, e)
        logger.info("ExplainSignalView: %d headline(s) sourced for %s",
                    len(headlines), signal.stock.symbol)

        try:
            # use_rag=False — building a RAG index needs PDFs (step 4 wires it).
            explanation = _explain(signal_dict, headlines=headlines, use_rag=False)
        except RuntimeError as e:
            # GEMINI_API_KEY missing, rate-limited past retries, etc.
            logger.error("ExplainSignalView: explain_signal failed for %s — %s",
                         signal.stock.symbol, e, exc_info=True)
            return Response({"error": str(e)},
                            status=status.HTTP_502_BAD_GATEWAY)

        cache.set(cache_key, explanation, timeout=self.CACHE_TTL)
        logger.info("ExplainSignalView: generated %d-char explanation for %s",
                    len(explanation), signal.stock.symbol)
        return Response(self._payload(signal, explanation, was_cached=False))

    @staticmethod
    def _payload(signal, explanation, *, was_cached):
        return {
            "symbol": signal.stock.symbol,
            "date": signal.date,
            "signal_type": signal.signal_type,
            "price": str(signal.price),  # Decimal -> str for JSON
            "rsi": signal.rsi,
            "macd": signal.macd,
            "technical_reason": signal.reason,
            "explanation": explanation,
            "cached": was_cached,
        }
