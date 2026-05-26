"""Week 3 — a multi-agent explainer.

One giant prompt that does everything is hard to steer and hard to debug. A
multi-agent design splits the work:

  Router            -> decides which specialist agents a question needs.
  TechnicalAgent    -> explains indicator state (RSI, MACD, ...).
  NewsAgent         -> explains recent news sentiment.
  FundamentalsAgent -> answers from earnings-call context via RAG.

The router picks the relevant agents, each specialist answers only its slice,
and a final synthesis step combines them into one answer.

INTERVIEW: this is the file agentic-AI interviews care about most. Talking
points — orchestration/routing, single-responsibility agents, graceful
degradation when one agent has no data, and how you would *evaluate* the
router's accuracy (a labelled set of questions -> expected agents).

Run (from week3/):  python -m llm.multi_agent
"""
from __future__ import annotations

import json
import logging
from typing import Any

from . import generate
from .rag import query_rag
from .sentiment import stock_sentiment

logger = logging.getLogger(__name__)


class TechnicalAgent:
    """Explains the technical-indicator state of a signal."""

    name = "technical"
    description = "indicator state — RSI, MACD, moving averages, the signal rule"

    def handle(self, question: str, context: dict) -> str:
        prompt = (f"You are a technical-analysis specialist. Using ONLY the "
                  f"technical context, answer in 2-3 sentences.\n"
                  f"Context: {context.get('technical', 'none provided')}\n"
                  f"Question: {question}\nAnswer:")
        return generate(prompt).strip()


class NewsAgent:
    """Explains recent news sentiment for the stock."""

    name = "news"
    description = "recent news and market sentiment about the stock"

    def handle(self, question: str, context: dict) -> str:
        symbol = context.get("symbol", "")
        headlines = context.get("headlines") or []
        if headlines:
            summary = stock_sentiment(symbol, headlines)
            sentiment = f"{summary['label']} (score {summary['score']})"
        else:
            sentiment = "no headlines available"
        prompt = (f"You are a market-news specialist. Using the sentiment "
                  f"summary, answer in 2-3 sentences.\n"
                  f"Sentiment for {symbol}: {sentiment}\n"
                  f"Question: {question}\nAnswer:")
        return generate(prompt).strip()


class FundamentalsAgent:
    """Answers from company fundamentals / earnings-call commentary via RAG."""

    name = "fundamentals"
    description = "company fundamentals and earnings-call commentary"

    def handle(self, question: str, context: dict) -> str:
        try:
            chunks = query_rag(question, top_k=3)
            evidence = "\n".join(f"[{c.source}] {c.text[:250]}" for c in chunks)
        except RuntimeError as e:
            evidence = f"no earnings data indexed ({e})"
        prompt = (f"You are a fundamentals specialist. Answer ONLY from the "
                  f"earnings-call evidence below; if it does not cover the "
                  f"question, say so plainly.\nEvidence:\n{evidence}\n"
                  f"Question: {question}\nAnswer:")
        return generate(prompt).strip()


# The agent registry — name -> instance. WHY `Any` instead of `object` here:
# every concrete agent has the same `name / description / handle` interface, so
# the router/synthesiser access those attributes uniformly. `object` would force
# us to declare a Protocol (or cast) at every access; `Any` keeps the route
# code readable. If the interface grows complex, lift to a `Protocol`.
AGENTS: dict[str, Any] = {
    agent.name: agent
    for agent in (TechnicalAgent(), NewsAgent(), FundamentalsAgent())
}


def route(question: str) -> list[str]:
    """Ask Gemini which specialist agents a question needs.

    Falls back to ALL agents if routing fails — better to over-answer than to
    silently drop a relevant specialist.
    """
    catalogue = "\n".join(f"- {a.name}: {a.description}" for a in AGENTS.values())
    prompt = (f"Given the agents below, return a JSON array of the agent NAMES "
              f"needed to answer the question. Pick only the relevant ones.\n"
              f"Agents:\n{catalogue}\n"
              f'Question: {question}\nJSON array (e.g. ["technical"]):')
    try:
        names = json.loads(generate(prompt, json_mode=True, temperature=0.0))
        chosen = [n for n in names if n in AGENTS]
        return chosen or list(AGENTS)
    except (json.JSONDecodeError, TypeError, RuntimeError) as e:
        logger.warning("router failed (%s) — falling back to all agents", e)
        return list(AGENTS)


def answer(question: str, context: dict) -> dict:
    """Route the question, run the chosen agents, synthesise one final answer.

    Args:
        question: the user's question.
        context: shared context — keys: symbol, technical, headlines.

    Returns:
        {question, agents_used, specialist_answers, answer}.
    """
    chosen = route(question)
    logger.info("multi_agent: '%s' routed to %s", question[:50], chosen)

    specialist_answers = {
        name: AGENTS[name].handle(question, context) for name in chosen
    }

    synthesis_prompt = (
        f"Combine these specialist answers into ONE coherent 2-4 sentence "
        f"response to the question. Do not repeat yourself.\n"
        f"Question: {question}\n"
        f"Specialist answers:\n{json.dumps(specialist_answers, indent=2)}\n"
        f"Combined answer:")
    final = generate(synthesis_prompt, temperature=0.3).strip()

    return {"question": question, "agents_used": chosen,
            "specialist_answers": specialist_answers, "answer": final}


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    demo_context = {
        "symbol": "RELIANCE.NS",
        "technical": "RSI 32 (oversold); MACD crossed above its signal line",
        "headlines": ["Reliance Q3 profit beats estimates on retail strength"],
    }
    try:
        result = answer("Why might this stock be a buy right now?", demo_context)
        print(json.dumps(result, indent=2))
    except RuntimeError as e:
        print(f"[skipped] {e}")
