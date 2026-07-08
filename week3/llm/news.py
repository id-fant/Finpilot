"""Week 3 — headline sources for the sentiment pipeline.

Returns `list[str]` — the exact shape `llm.sentiment.stock_sentiment` and
`llm.explainer.explain_signal` expect, so this drops in with no adapter.

Two free sources, combined and de-duplicated:
  1. yfinance.Ticker(symbol).news — per-ticker, NSE-aware via the .NS suffix.
  2. Zerodha Pulse RSS            — broad Indian-finance aggregator; filtered
                                    to headlines mentioning the symbol stem.

WHY combine: yfinance is per-stock but flaky and sparse; Pulse is reliable and
dense but unfiltered. Together you get coverage without the noise of a
firehose. Either source can fail silently — `headlines_for` never raises, so a
network blip cannot kill the surrounding explain/sentiment call.

Run (from week3/):  python -m llm.news RELIANCE.NS
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

# feedparser is the ONLY new dependency; guarded so this module imports cleanly
# even without it (the yfinance path still works on its own).
# `Any`-typed so the use sites below are not flagged on `feedparser = None` —
# see llm/__init__.py for the same pattern.
feedparser: Any
try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    feedparser = None
    _HAS_FEEDPARSER = False

# yfinance is already a project dep (week1 + week2 + week4 use it).
yf: Any
try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    yf = None
    _HAS_YF = False

PULSE_FEED = "https://pulse.zerodha.com/feed.php"
MAX_PULSE_SCAN = 200  # entries to look through before stopping the filter

# WHY cache the Pulse feed: it is ONE aggregator feed, not per-symbol — only
# the client-side filter differs. A batch run (8 tracked stocks) would
# otherwise download + parse the identical feed 8 times. 10 minutes is well
# inside the freshness needs of a once-a-day signal run.
_PULSE_CACHE_TTL = 600.0  # seconds
_pulse_cache: tuple[float, Any] | None = None  # (fetched_at, parsed feed)


def _fetch_pulse_feed() -> Any:
    """Parsed Pulse RSS feed, cached across symbols for _PULSE_CACHE_TTL.

    WHY the manual fetch: feedparser calls urllib with the default TLS
    context, which under antivirus HTTPS interception (Avast) either can't
    find the re-signing root or — on Python 3.13 — rejects it as not
    strict-compliant. We fetch the bytes ourselves through the same relaxed
    context the Gemini client uses (`llm._ssl_context`), then hand the bytes
    to feedparser. On a machine without interception `_ssl_context()` returns
    None and we fall back to feedparser's own fetch.
    """
    global _pulse_cache
    now = time.monotonic()
    if _pulse_cache is not None and now - _pulse_cache[0] < _PULSE_CACHE_TTL:
        return _pulse_cache[1]

    ctx = None
    try:
        from . import _ssl_context
        ctx = _ssl_context()
    except Exception:  # noqa: BLE001 - fall back to plain fetch
        ctx = None

    if ctx is not None:
        import urllib.request
        req = urllib.request.Request(
            PULSE_FEED, headers={"User-Agent": "Mozilla/5.0 (FinPilot)"})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
        # pyrefly: ignore[missing-attribute] -- guarded by _HAS_FEEDPARSER at call site
        feed = feedparser.parse(data)
    else:
        # pyrefly: ignore[missing-attribute] -- guarded by _HAS_FEEDPARSER at call site
        feed = feedparser.parse(PULSE_FEED)
    _pulse_cache = (now, feed)
    return feed


def _yfinance_headlines(symbol: str, limit: int) -> list[str]:
    """Per-ticker news titles from yfinance. Returns at most `limit` titles."""
    if not _HAS_YF:
        return []
    try:
        # pyrefly: ignore[missing-attribute] -- guarded by _HAS_YF above
        items = yf.Ticker(symbol).news or []
    except Exception as e:  # noqa: BLE001 - yfinance raises a lot of error types
        logger.warning("news: yfinance.news(%s) failed — %s", symbol, e)
        return []

    out: list[str] = []
    for item in items[:limit]:
        # yfinance's payload shape shifted across versions — handle both:
        # newer responses nest under 'content', older have title at top level.
        title = (
            (item.get("content") or {}).get("title")
            or item.get("title")
            or ""
        ).strip()
        if title:
            out.append(title)
    return out


def _pulse_headlines(symbol_stem: str, limit: int, seen: set[str]) -> list[str]:
    """Zerodha Pulse RSS, filtered to headlines containing `symbol_stem`."""
    if not _HAS_FEEDPARSER:
        return []
    try:
        feed = _fetch_pulse_feed()
    except Exception as e:  # noqa: BLE001
        logger.warning("news: Pulse RSS fetch failed — %s", e)
        return []

    needle = symbol_stem.upper()
    out: list[str] = []
    for entry in feed.entries[:MAX_PULSE_SCAN]:
        title = (entry.get("title") or "").strip()
        if not title or title in seen:
            continue
        if needle in title.upper():
            out.append(title)
            if len(out) >= limit:
                break
    return out


def _pulse_items(limit: int, symbol_stem: str | None = None) -> list[dict]:
    """Pulse entries as {title, link, source}, optionally filtered by stem.

    The richer sibling of `_pulse_headlines` — keeps the LINK so the dashboard
    News view can open the source article (headlines_for() drops it because
    the sentiment/explainer callers only need the title string).
    """
    if not _HAS_FEEDPARSER:
        return []
    try:
        feed = _fetch_pulse_feed()
    except Exception as e:  # noqa: BLE001
        logger.warning("news: Pulse RSS fetch failed — %s", e)
        return []
    needle = symbol_stem.upper() if symbol_stem else None
    out: list[dict] = []
    for entry in feed.entries[:MAX_PULSE_SCAN]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        if needle and needle not in title.upper():
            continue
        out.append({"title": title, "link": entry.get("link", ""),
                    "source": "Zerodha Pulse"})
        if len(out) >= limit:
            break
    return out


def news_items(symbol: str | None = None, *, limit: int = 15) -> list[dict]:
    """Recent news as [{title, link, source}] — the dashboard News feed.

    symbol=None returns the broad Indian-market Pulse feed (unfiltered); a
    symbol returns that stock's Yahoo Finance items plus Pulse headlines that
    name it. De-duplicated by title, best-effort (never raises — an empty list
    means "no news available", the same contract as headlines_for).
    """
    if not symbol:
        return _pulse_items(limit)

    items: list[dict] = []
    if _HAS_YF:
        try:
            # pyrefly: ignore[missing-attribute] -- guarded by _HAS_YF above
            raw = yf.Ticker(symbol).news or []
        except Exception as e:  # noqa: BLE001 - yfinance raises many error types
            logger.warning("news: yfinance.news(%s) failed — %s", symbol, e)
            raw = []
        for it in raw[:limit]:
            content = it.get("content") or {}
            title = (content.get("title") or it.get("title") or "").strip()
            link = ((content.get("clickThroughUrl") or {}).get("url")
                    or (content.get("canonicalUrl") or {}).get("url")
                    or it.get("link") or "")
            if title:
                items.append({"title": title, "link": link,
                              "source": "Yahoo Finance"})

    items.extend(_pulse_items(limit, symbol.split(".")[0]))

    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        out.append(it)
        if len(out) >= limit:
            break
    logger.info("news_items(%s): %d item(s)", symbol or "market", len(out))
    return out


def headlines_for(symbol: str, *, limit: int = 15) -> list[str]:
    """Recent headlines for `symbol`, de-duplicated, newest first.

    Args:
        symbol: NSE ticker, e.g. "RELIANCE.NS". The Pulse filter strips the
            ".NS"/".BO" suffix to match bare stems in headlines.
        limit: cap on the returned list.

    Returns:
        A list of plain headline strings. Empty if both sources are unavailable —
        callers must treat empty as "no news supplied", not as an error.
    """
    seen: set[str] = set()
    out: list[str] = []

    # 1. yfinance per-ticker.
    for title in _yfinance_headlines(symbol, limit):
        if title not in seen:
            seen.add(title)
            out.append(title)
            if len(out) >= limit:
                break

    # 2. Pulse — only if we still need more after yfinance.
    if len(out) < limit:
        stem = symbol.split(".")[0]
        for title in _pulse_headlines(stem, limit - len(out), seen):
            if title not in seen:
                seen.add(title)
                out.append(title)
                if len(out) >= limit:
                    break

    logger.info("headlines_for(%s): %d headline(s) (yfinance + Pulse)",
                symbol, len(out))
    return out


if __name__ == "__main__":  # quick demo: python -m llm.news RELIANCE.NS
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(name)s: %(message)s")
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
    for i, h in enumerate(headlines_for(sym, limit=10), 1):
        print(f"{i:2d}. {h}")
