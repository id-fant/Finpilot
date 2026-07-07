"""Celery tasks for the `signals` app."""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from core.data import fetch_ohlcv
from core.ml_gate import score_signal
from core.strategy import generate_signal

logger = logging.getLogger(__name__)

# Optional LLM enrichment — week3's explainer fills Signal.reason with a
# plain-English, news-aware explanation. Guarded so week2 still works if
# week3 is absent or GEMINI_API_KEY is not set — the technical reason from
# core.strategy is the always-safe fallback.
# Same `Any`-typed pattern as the rest of the project: see week3/llm/__init__.py.
explain_signal: Any
headlines_for: Any
try:
    from llm.explainer import explain_signal  # pyrefly: ignore[missing-import]
    from llm.news import headlines_for  # pyrefly: ignore[missing-import]
    _HAS_LLM = True
except ImportError:
    explain_signal = None
    headlines_for = None
    _HAS_LLM = False


def _is_llm_reason(reason: str) -> bool:
    """True if `reason` is LLM prose rather than the engine's technical string.

    The engine's format is fixed — "BUY: ...", "SELL: ...", "HOLD (...)" (see
    core/strategy.py) — so anything else came from the week3 explainer. Used
    to decide whether today's stored Signal already carries an explanation.
    """
    return bool(reason) and not reason.startswith(("BUY:", "SELL:", "HOLD ("))


def _enrich_reason(symbol: str, result: dict) -> str:
    """Return the LLM explanation if week3 is wired up; else the technical reason.

    Four layers of fallback — the task NEVER fails because of LLM trouble:
      0. GEMINI_API_KEY unset            -> technical reason (zero network)
      1. week3 not importable            -> technical reason
      2. headlines fetch fails           -> proceed with `None` (explainer copes)
      3. Gemini call fails / rate-limits -> log + fall back to technical reason

    The result is that `Signal.reason` is always populated with something
    useful: news-grounded prose when the LLM is available, the bare
    technical rule when it isn't.

    WHY the GEMINI_API_KEY pre-check: without it, `generate()` retries 4x with
    2/4/8/16s backoff on every failure — across 8 stocks that's minutes of
    wall time just to discover the key isn't set. The pre-check makes the
    common "no key configured" path instant, which is what `smoke_test.py`
    and CI both depend on.
    """
    import os
    if not _HAS_LLM or not os.environ.get("GEMINI_API_KEY"):
        return result["reason"]
    try:
        try:
            # pyrefly: ignore[not-callable] -- guarded by _HAS_LLM above
            headlines = headlines_for(symbol, limit=5)
        except Exception as e:  # noqa: BLE001 - news is best-effort
            logger.debug("headlines_for(%s) failed: %s", symbol, e)
            headlines = None
        # use_rag=False here: most stocks have no earnings PDF indexed; the
        # explainer logs a warning and falls back to technical+news alone.
        # Flip to True once the RAG index is built (see week3/llm/rag.py).
        # pyrefly: ignore[not-callable] -- guarded by _HAS_LLM above
        return explain_signal(result, headlines=headlines, use_rag=False)
    except Exception as e:  # noqa: BLE001 - LLM failure must not break the batch
        logger.warning("explain_signal(%s) failed (%s) — using technical reason",
                       symbol, e)
        return result["reason"]


@shared_task(name="signals.generate_daily_signals")
def generate_daily_signals() -> dict:
    """Generate today's signal for every tracked stock.

    Celery Beat schedules this to run after market open (09:05 IST). It can
    also be called directly — `generate_daily_signals()` — which runs it
    synchronously, handy for the smoke test and for local debugging.

    INTERVIEW — idempotency: a scheduled task may be retried, or fired twice by
    accident. This task uses `update_or_create` keyed on (stock, date), so a
    second run UPDATES today's row rather than inserting a duplicate. Backed by
    the model's `unique_together = [["stock", "date"]]` constraint, running it
    N times leaves the database in exactly the same state as running it once.

    Returns:
        A summary dict: count written, list of failed symbols, total tracked.
    """
    # WHY import models INSIDE the function, not at module top: Celery imports
    # this tasks.py very early during startup (autodiscover_tasks). A top-level
    # `from .models import ...` can execute before Django's app registry is
    # ready and raise AppRegistryNotReady. Importing here defers it until the
    # task actually runs, by which point the registry is loaded.
    from .models import Signal, Stock

    # WHY list(...) once: the queryset is needed three times — to count, to
    # iterate, and to report the total. Evaluating it into a list runs ONE
    # SELECT; calling .count() twice plus iterating would run three queries
    # for the same rows. (Same query-economy lesson as select_related — #27.)
    tracked = list(Stock.objects.filter(is_tracked=True))
    total_tracked = len(tracked)
    logger.info("generate_daily_signals: starting run for %d tracked stock(s)",
                total_tracked)
    written = 0
    failures: list[str] = []

    for stock in tracked:
        logger.debug("generate_daily_signals: processing %s", stock.symbol)
        try:
            # WHY 1y (was 6mo): the ML gate's dist_sma200 feature needs 200
            # bars of history. The indicators themselves are unchanged — RSI/
            # MACD/Bollinger only look back ~26 bars either way.
            df = fetch_ohlcv(stock.symbol, period="1y")
            result = generate_signal(df, stock.symbol)
            # Meta-labeling score for BUY entries (the only side the live
            # system trades). None = gate not in play (no model / failure) —
            # stored as NULL, which downstream treats as "unscored", never 0.
            ml_prob = (score_signal(df, result["buy_votes"])
                       if result["signal"] == "BUY" else None)
            # WHY reuse today's explanation when the verdict is unchanged:
            # Gemini's free tier is metered PER DAY (e.g. 20 requests). The
            # supervisor re-runs this task every cycle — re-explaining an
            # unchanged HOLD each time would burn the whole day's quota in
            # two cycles. The Signal row is the cache: same date + same
            # verdict + an LLM-shaped reason ⇒ keep it. A verdict CHANGE
            # (HOLD→BUY) still triggers a fresh explanation.
            existing = Signal.objects.filter(
                stock=stock, date=result["date"]).first()
            if (existing is not None
                    and existing.signal_type == result["signal"]
                    and _is_llm_reason(existing.reason)):
                reason = existing.reason
                logger.debug("generate_daily_signals: %s reusing today's "
                             "LLM explanation (verdict unchanged)", stock.symbol)
            else:
                reason = _enrich_reason(stock.symbol, result)
            _, created = Signal.objects.update_or_create(
                stock=stock,
                date=result["date"],
                # `defaults` are the fields written on create OR update; the
                # lookup fields (stock, date) above identify the unique row.
                defaults={
                    "signal_type": result["signal"],
                    "price": result["price"],
                    "rsi": result["rsi"],
                    "macd": result["macd"],
                    "macd_signal": result["macd_signal"],
                    "reason": reason,
                    "ml_prob": ml_prob,
                },
            )
            written += 1
            logger.info("generate_daily_signals: %s -> %s @ %s [%s]",
                        stock.symbol, result["signal"], result["price"],
                        "created" if created else "updated")
        except Exception as e:  # noqa: BLE001 - one bad ticker must not abort the batch
            # WHY exc_info=True: it logs the FULL traceback, so you can see
            # exactly WHERE the failure happened — the single most useful thing
            # when pinpointing a runtime issue, not just that one occurred.
            logger.error("generate_daily_signals: FAILED for %s — %s",
                          stock.symbol, e, exc_info=True)
            failures.append(stock.symbol)

    summary = {
        "written": written,
        "failed": failures,
        "total_tracked": total_tracked,
    }
    # WARNING if anything failed — so a partially-broken run is visible at a
    # glance in the logs, distinct from a clean run.
    if failures:
        logger.warning("generate_daily_signals: run finished with %d failure(s): %s",
                        len(failures), failures)
    logger.info("generate_daily_signals: run complete — %s", summary)
    return summary
