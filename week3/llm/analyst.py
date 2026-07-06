"""Week 3 — the LLM analyst gate.

The piece that makes the pipeline *agentic* rather than merely scheduled: when
the technical engine proposes a BUY/SELL, an LLM "analyst" reviews the trade
in context — the indicator evidence, fresh headlines, current portfolio state —
and returns a STRUCTURED verdict before any order reaches the broker.

Design rules (the part interviews care about):

  1. The LLM GATES decisions, it does not MAKE them. The deterministic engine
     proposes; the analyst can only approve, veto, or shrink a trade the rules
     already produced. It can never invent a trade, pick a size, or touch the
     broker. Bounded authority is what makes an LLM safe near money.
  2. Structured output only — a JSON verdict with a fixed schema, never prose
     we would have to parse. Same discipline as sentiment.py / evaluation.py.
  3. Fail-open is the CALLER's policy, not ours. This module raises on LLM
     failure (like explainer.py); the Django adapter decides that "analyst
     unavailable" means "proceed on technical rules alone". Policy lives with
     the framework, mechanics live here — ports and adapters again.

INTERVIEW — "how would you use an LLM in a trading system safely?" This file
is the answer: bounded action space, structured verdicts, deterministic risk
gates AFTER the LLM (OrderManager's caps still apply to whatever it approves),
and a journal row per decision so every verdict is auditable later.

Run (from week3/):  python -m llm.analyst
"""
from __future__ import annotations

import json
import logging

from . import generate

logger = logging.getLogger(__name__)

# The only actions the analyst may take. Anything else in the response is
# coerced to "approve" — an LLM must not gain new powers via a typo.
VERDICTS = ("approve", "veto", "reduce")

_PROMPT = """You are a conservative equity trade reviewer for an Indian (NSE)
systematic strategy. A rule-based engine has proposed the trade below. Your
job is NOT to find new trades — only to catch reasons this one should not run
at full size today.

Proposed trade:
  {action} {symbol} at approximately Rs.{price}
  Technical evidence: {reason}

Recent headlines (may be empty):
{headlines}

Current portfolio: {portfolio}

Decision policy:
- "approve": the default. Technical evidence stands and nothing contradicts it.
- "reduce": genuine uncertainty — mixed/negative news against a BUY, earnings
  or a major binary event imminent, or the portfolio is already concentrated
  in this name or sector. Trade runs at half size.
- "veto": clear, citable contradiction — e.g. fraud/regulatory action in the
  headlines against a BUY, or the trade duplicates an existing position the
  portfolio already holds in the same direction.

Do not veto merely because markets are risky in general. Cite your evidence.

Return ONLY a JSON object, no extra text:
{{"verdict": "approve|veto|reduce", "confidence": <float 0.0-1.0>,
  "rationale": "<1-2 sentences citing the specific evidence>"}}"""


def review_trade(signal: dict, *, headlines: list[str] | None = None,
                 portfolio: dict | None = None) -> dict:
    """Review one proposed trade and return a structured verdict.

    Args:
        signal: the engine's signal dict — needs keys symbol, signal (BUY/SELL),
            price, reason. Same shape core.strategy.generate_signal emits.
        headlines: recent headlines for the stock (best-effort, may be None).
        portfolio: current portfolio state, e.g. {"open_symbols": [...]}.
            Kept as a plain dict so this module stays framework-free.

    Returns:
        {"verdict": "approve"|"veto"|"reduce", "confidence": float,
         "rationale": str} — verdict is ALWAYS one of VERDICTS.

    Raises:
        RuntimeError: if the LLM call fails after retries (missing key, rate
            limit, ...). Callers choose the fallback policy — see
            portfolio/tasks.py, which fails OPEN to the technical rules.
    """
    headline_block = ("\n".join(f"- {h}" for h in headlines)
                      if headlines else "- (none available)")
    prompt = _PROMPT.format(
        action=signal.get("signal", "?"),
        symbol=signal.get("symbol", "?"),
        price=signal.get("price", "?"),
        reason=signal.get("reason", "no technical reason supplied"),
        headlines=headline_block,
        portfolio=json.dumps(portfolio or {}),
    )

    # temperature=0.0 — a risk gate must be as deterministic as an LLM gets;
    # two runs over the same evidence should reach the same verdict.
    raw = generate(prompt, json_mode=True, temperature=0.0)

    try:
        parsed = json.loads(raw)
        verdict = str(parsed.get("verdict", "")).strip().lower()
        confidence = float(parsed.get("confidence", 0.0))
        rationale = str(parsed.get("rationale", "")).strip()
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # A malformed verdict must not become a silent veto — approve with a
        # flagged rationale so the journal shows the gate misfired.
        logger.error("analyst: unparseable verdict (%s) — defaulting to approve", e)
        return {"verdict": "approve", "confidence": 0.0,
                "rationale": f"analyst response unparseable ({e}); "
                             "proceeding on technical rules"}

    if verdict not in VERDICTS:
        logger.warning("analyst: unknown verdict %r — coerced to approve", verdict)
        rationale = f"unknown verdict {verdict!r} coerced to approve; {rationale}"
        verdict, confidence = "approve", 0.0

    result = {"verdict": verdict,
              "confidence": max(0.0, min(confidence, 1.0)),
              "rationale": rationale or "no rationale given"}
    logger.info("analyst: %s %s -> %s (%.2f) — %s",
                signal.get("signal"), signal.get("symbol"),
                result["verdict"], result["confidence"], result["rationale"])
    return result


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(name)s: %(message)s")
    demo_signal = {
        "symbol": "RELIANCE.NS", "signal": "BUY", "price": 1354.50,
        "reason": "BUY: RSI 32 oversold (<35); price below the lower Bollinger Band",
    }
    demo_headlines = [
        "Reliance Q3 profit beats estimates on strong retail growth",
        "SEBI opens inquiry into Reliance subsidiary disclosures",
    ]
    try:
        verdict = review_trade(demo_signal, headlines=demo_headlines,
                               portfolio={"open_symbols": ["TCS.NS"]})
        print(json.dumps(verdict, indent=2))
    except RuntimeError as e:
        print(f"[skipped] {e}")
