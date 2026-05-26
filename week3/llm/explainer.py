"""Week 3 — the signal explainer.

Combines three context sources into one plain-English explanation of a signal:
  1. the technical state (RSI, MACD, the rule that fired),
  2. recent news sentiment for the stock,
  3. relevant earnings-call context retrieved via RAG.

`explain_signal()` produces the text that fills the `reason` field on week2's
Signal model.

WHY this takes a plain dict, not week2's `Signal` model: it keeps this package
Django-free. week2's view/task builds the dict from its model and passes it in
— the framework stays an adapter around a framework-agnostic core.

Run (from week3/):  python -m llm.explainer
"""
from __future__ import annotations

import logging

from . import generate
from .rag import query_rag
from .sentiment import stock_sentiment

logger = logging.getLogger(__name__)

_TEMPLATE = """You are an equity-research assistant. In 2-3 plain-English
sentences, explain WHY this trading signal fired, for a retail investor. Be
specific and grounded ONLY in the data below. Do NOT give financial advice or
invent facts.

SIGNAL
  Stock      : {symbol}
  Signal     : {signal}
  Price      : {price}
  Technicals : {technical}

NEWS SENTIMENT
  {sentiment}

EARNINGS-CALL CONTEXT (retrieved)
  {rag}

Explanation:"""


def explain_signal(signal: dict, headlines: list[str] | None = None,
                   use_rag: bool = True) -> str:
    """Generate a plain-English explanation for one signal.

    Args:
        signal: a dict shaped like core.strategy.generate_signal()'s output —
            keys: symbol, signal, price, rsi, macd, reason.
        headlines: optional recent news headlines; enables the sentiment block.
        use_rag: if True, retrieve earnings-call context (needs a built index).

    Returns:
        A 2-3 sentence explanation string.
    """
    symbol = signal["symbol"]
    technical = (f"RSI={signal.get('rsi')}, MACD={signal.get('macd')}; "
                 f"rule fired: {signal.get('reason', 'n/a')}")

    # 2. News sentiment — only if headlines were supplied.
    sentiment_text = "no recent news supplied"
    if headlines:
        summary = stock_sentiment(symbol, headlines)
        sentiment_text = (f"{summary['label']} (score {summary['score']}, "
                          f"from {summary['n_headlines']} headlines)")

    # 3. RAG context — degrade gracefully if no index has been built.
    rag_text = "not retrieved"
    if use_rag:
        try:
            chunks = query_rag(
                f"recent business performance and outlook for {symbol}", top_k=3)
            rag_text = "\n  ".join(
                f"[{c.source}] {c.text[:200]}..." for c in chunks) or "no chunks found"
        except RuntimeError as e:
            logger.warning("explain_signal(%s): RAG unavailable — %s", symbol, e)
            rag_text = f"unavailable ({e})"

    prompt = _TEMPLATE.format(
        symbol=symbol, signal=signal["signal"], price=signal.get("price"),
        technical=technical, sentiment=sentiment_text, rag=rag_text)

    explanation = generate(prompt, temperature=0.3).strip()
    logger.info("explain_signal(%s): generated a %d-char explanation",
                symbol, len(explanation))
    return explanation


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    demo_signal = {
        "symbol": "RELIANCE.NS", "signal": "BUY", "price": 1354.5,
        "rsi": 32.1, "macd": 4.2,
        "reason": "BUY: RSI 32 oversold (<35); MACD crossed above its signal line",
    }
    demo_headlines = [
        "Reliance Q3 profit beats estimates on strong retail growth",
        "Analysts raise Reliance target price after earnings",
    ]
    try:
        print(explain_signal(demo_signal, headlines=demo_headlines, use_rag=False))
    except RuntimeError as e:
        print(f"[skipped] {e}")
