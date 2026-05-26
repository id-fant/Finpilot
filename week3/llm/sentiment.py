"""Week 3 — news sentiment scoring with Gemini.

Pipeline:
  1. Take a list of news headlines for a stock.
  2. Batch them (10 at a time) and ask Gemini to score each — returning
     STRUCTURED JSON, never free text we would have to parse with regex.
  3. Aggregate the per-headline scores into one number in [-1, +1].

A file cache keyed by headline avoids paying for the same Gemini call twice.

WHY a file cache, not the Django DB the spec mentions: it keeps this package
framework-free (no ORM import) and runnable on its own. week2 can wrap this and
persist to a model later if a shared, cross-process cache is needed.

Run (from the week3/ folder):  python -m llm.sentiment
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from . import generate

logger = logging.getLogger(__name__)

# Cache lives under week3/.cache/ (git-ignored).
CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "sentiment.json"
BATCH_SIZE = 10  # WHY batch: one Gemini call for 10 headlines, not 10 calls.

_PROMPT = """You are a financial news analyst scoring headlines for the stock
{symbol}, from an equity investor's perspective.

Score EACH headline. Return ONLY a JSON array with one object per headline,
IN THE SAME ORDER as given, with no extra text:
[{{"score": <float -1.0 very bearish to 1.0 very bullish>, "label": "<positive|neutral|negative>"}}]

Headlines:
{headlines}"""


def _headline_key(headline: str) -> str:
    """Stable cache key — a hash, so headline length/punctuation don't matter."""
    return hashlib.sha1(headline.strip().lower().encode()).hexdigest()[:16]


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _score_batch(headlines: list[str], symbol: str) -> list[dict]:
    """Score one batch (<= BATCH_SIZE headlines) with a single Gemini call."""
    numbered = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(headlines))
    raw = generate(_PROMPT.format(symbol=symbol, headlines=numbered),
                   json_mode=True, temperature=0.1)
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or len(parsed) != len(headlines):
            raise ValueError(f"expected {len(headlines)} scores, got {len(parsed)}")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        # Degrade gracefully — a parse failure scores the batch neutral rather
        # than crashing the whole pipeline.
        logger.error("sentiment: batch parse failed (%s) — scoring it neutral", e)
        parsed = [{"score": 0.0, "label": "neutral"}] * len(headlines)

    return [{"headline": h,
             "score": float(p.get("score", 0.0)),
             "label": p.get("label", "neutral")}
            for h, p in zip(headlines, parsed)]


def score_headlines(headlines: list[str], symbol: str) -> list[dict]:
    """Score every headline — cache hits are reused, misses are batched."""
    cache = _load_cache()
    results: dict[str, dict] = {}
    uncached: list[str] = []

    for headline in headlines:
        key = _headline_key(headline)
        if key in cache:
            results[headline] = {"headline": headline, **cache[key]}
        else:
            uncached.append(headline)

    logger.info("sentiment(%s): %d headline(s) — %d cached, %d to score",
                symbol, len(headlines), len(headlines) - len(uncached), len(uncached))

    for start in range(0, len(uncached), BATCH_SIZE):
        batch = uncached[start:start + BATCH_SIZE]
        for scored in _score_batch(batch, symbol):
            results[scored["headline"]] = scored
            cache[_headline_key(scored["headline"])] = {
                "score": scored["score"], "label": scored["label"]}

    if uncached:
        _save_cache(cache)

    # Return in the caller's original order.
    return [results[h] for h in headlines]


def aggregate(scored: list[dict]) -> float:
    """Mean of the per-headline scores — the stock's sentiment in [-1, +1]."""
    if not scored:
        return 0.0
    return round(sum(s["score"] for s in scored) / len(scored), 3)


def stock_sentiment(symbol: str, headlines: list[str]) -> dict:
    """Top-level entry point: score a stock's headlines, return an aggregate.

    Returns:
        {symbol, score (-1..1), label, n_headlines, headlines: [per-headline]}.
    """
    scored = score_headlines(headlines, symbol)
    score = aggregate(scored)
    label = ("positive" if score > 0.15
             else "negative" if score < -0.15 else "neutral")
    logger.info("sentiment(%s): aggregate score %.3f (%s)", symbol, score, label)
    return {"symbol": symbol, "score": score, "label": label,
            "n_headlines": len(headlines), "headlines": scored}


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    demo_headlines = [
        "Reliance Q3 profit beats estimates on strong retail growth",
        "Reliance shares slip as oil-to-chemicals margins narrow",
        "Reliance announces major new green-energy investment",
    ]
    try:
        result = stock_sentiment("RELIANCE.NS", demo_headlines)
        print(json.dumps(result, indent=2))
    except RuntimeError as e:
        print(f"[skipped] {e}")
