"""Week 3 — RAG evaluation (RAGAS-style metrics).

You cannot improve what you do not measure. This module scores the RAG pipeline
on the three standard RAGAS metrics, using an LLM as the judge:

  faithfulness       — is every claim in the answer grounded in the retrieved
                       context (no hallucination)?            0.0 - 1.0
  answer_relevance   — does the answer actually address the question?  0.0 - 1.0
  context_relevance  — were the retrieved chunks relevant to the question? 0-1

WHY implement the metrics here instead of importing the `ragas` package: ragas
pulls a large dependency tree (LangChain, datasets, ...) and changes often.
Computing the three metrics directly with Gemini-as-judge is lighter, adds no
dependency, and — more useful for learning — makes each definition explicit.

INTERVIEW — "how do you evaluate an LLM system?": you cannot assert equality on
open-ended text. You define metrics up front (faithfulness, relevance), score
every change against a fixed question set, and watch for regressions. An
LLM-as-judge is cheap and scalable, but should itself be checked against human
labels.

Run (from week3/):  python -m llm.evaluation
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import generate
from .rag import query_rag

logger = logging.getLogger(__name__)

# 10 sample questions for benchmarking. `expected` is a human-review reference
# describing the KIND of answer a good earnings corpus should yield.
SAMPLE_QUESTIONS = [
    {"question": "What did management say about revenue growth this quarter?",
     "expected": "A figure or direction for revenue growth, with management's reasoning."},
    {"question": "What are the main risks management highlighted?",
     "expected": "Named risks — macro, demand, input costs, regulatory, etc."},
    {"question": "How are the company's margins trending?",
     "expected": "Gross/operating margin direction and the drivers behind it."},
    {"question": "What is the guidance or outlook for the next quarter?",
     "expected": "Forward-looking guidance, or a note that none was given."},
    {"question": "What did management say about capital expenditure?",
     "expected": "Planned capex, projects, or investment priorities."},
    {"question": "How is the company managing its debt?",
     "expected": "Debt levels, deleveraging plans, or refinancing commentary."},
    {"question": "What new products or business segments were discussed?",
     "expected": "Named launches, segments, or expansion areas."},
    {"question": "What did management say about demand conditions?",
     "expected": "Demand trends by segment or geography."},
    {"question": "How did the company perform versus expectations?",
     "expected": "Beat/miss/in-line versus estimates, with context."},
    {"question": "What is management's view on the competitive landscape?",
     "expected": "Competitive pressures, market share, or differentiation."},
]

CRITERIA = {
    "faithfulness":
        "Every claim in the Answer is supported by the Retrieved context "
        "(no invented or contradicted facts).",
    "answer_relevance":
        "The Answer directly and fully addresses the Question.",
    "context_relevance":
        "The Retrieved context is relevant and useful for answering the Question.",
}

_JUDGE_PROMPT = """You are a strict evaluation judge. Score the criterion below
from 0.0 (fails completely) to 1.0 (fully satisfied).
Return ONLY JSON: {{"score": <float>, "reason": "<one short sentence>"}}

Criterion: {criterion}

Question: {question}

Retrieved context:
{context}

Answer: {answer}"""


def _judge(criterion: str, question: str, context: str, answer_text: str) -> dict:
    """Score one criterion for one (question, context, answer) triple."""
    raw = generate(_JUDGE_PROMPT.format(criterion=criterion, question=question,
                                        context=context, answer=answer_text),
                   json_mode=True, temperature=0.0)
    try:
        result = json.loads(raw)
        return {"score": float(result.get("score", 0.0)),
                "reason": result.get("reason", "")}
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.error("evaluation: judge returned invalid JSON for '%s'", criterion)
        return {"score": 0.0, "reason": "judge returned invalid JSON"}


def evaluate_question(question: str, top_k: int = 5) -> dict:
    """Run the RAG pipeline for one question and score all three metrics."""
    chunks = query_rag(question, top_k=top_k)
    context = "\n".join(c.text for c in chunks)

    # Generate an answer grounded ONLY in the retrieved context — the same
    # constraint a faithful RAG system runs under.
    answer_text = generate(
        f"Answer the question using ONLY the context. If the context does not "
        f"cover it, say so.\nContext:\n{context}\nQuestion: {question}\nAnswer:"
    ).strip()

    detail = {name: _judge(criterion, question, context, answer_text)
              for name, criterion in CRITERIA.items()}
    scores = {name: detail[name]["score"] for name in CRITERIA}
    logger.info("evaluate_question: '%s' -> %s", question[:45], scores)
    return {"question": question, "answer": answer_text,
            "scores": scores, "detail": detail}


def run_evaluation(questions: list[str] | None = None,
                   output: str = "evaluation_report.json") -> dict:
    """Evaluate every question, aggregate the metrics, and write a JSON report.

    Returns:
        {n_questions, aggregate: {metric: mean_score}, results: [...]}.
    """
    questions = questions or [q["question"] for q in SAMPLE_QUESTIONS]
    results = []
    for question in questions:
        try:
            results.append(evaluate_question(question))
        except RuntimeError as e:
            logger.error("evaluation: skipping '%s' — %s", question[:45], e)

    aggregate = {}
    for metric in CRITERIA:
        values = [r["scores"][metric] for r in results]
        aggregate[metric] = round(sum(values) / len(values), 3) if values else 0.0

    report = {"n_questions": len(results), "aggregate": aggregate, "results": results}
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("evaluation: report written to %s — aggregate %s", output, aggregate)
    return report


if __name__ == "__main__":  # demo — needs GEMINI_API_KEY and a built RAG index
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
    try:
        report = run_evaluation()
        print(json.dumps(report["aggregate"], indent=2))
    except RuntimeError as e:
        print(f"[skipped] {e} — build a RAG index first (see llm/rag.py)")
