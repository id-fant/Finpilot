# FinPilot — Week 3: LLM Layer

Weeks 1-2 produced *signals*. A signal tells you **what** changed, not **why**.
Week 3 adds the *why*: every signal gets an AI-generated, plain-English
explanation grounded in real news and earnings-call data.

## Layout

```
week3/
├── requirements.txt
└── llm/                     framework-free package (no Django imports)
    ├── __init__.py          Gemini client + retry/backoff (shared)
    ├── sentiment.py         news headlines  -> Gemini -> per-stock score
    ├── rag.py               earnings PDFs   -> chunks -> embeddings -> search
    ├── explainer.py         technical + sentiment + RAG -> one explanation
    ├── multi_agent.py       router + 3 specialist agents
    └── evaluation.py        RAGAS-style metrics (faithfulness / relevance)
```

The `llm/` package is **framework-free** — like week2's `core/`, it is a pure
library callable from Django, a Celery task, a notebook or a test.

## Setup

```bash
cd week3
pip install -r requirements.txt
```

Create a `.env` in `week3/` (or export the variable):

```
GEMINI_API_KEY=your-key-here
```

Get a key at https://aistudio.google.com/apikey (free tier is enough to start).

> **faiss-cpu** is a ~30 MB native package. It normally installs from a prebuilt
> wheel — but if it fails, just remove the `faiss-cpu` line: `rag.py` falls back
> to a NumPy search automatically.

## The five modules

| Module | What it does | Key idea |
|--------|--------------|----------|
| `sentiment.py` | scores news headlines, aggregates to one score in [-1,+1] | structured JSON output, batching, a file cache |
| `rag.py` | indexes earnings PDFs, retrieves relevant passages | chunk → embed → vector search (FAISS or NumPy) |
| `explainer.py` | combines technical + sentiment + RAG into one explanation | grounding an LLM so it does not hallucinate |
| `multi_agent.py` | router picks specialist agents; answers are synthesised | orchestration / single-responsibility agents |
| `evaluation.py` | scores RAG on faithfulness / answer- & context-relevance | LLM-as-judge; measure before you optimise |

## Run the modules

Run them as package modules from inside `week3/`:

```bash
python -m llm.sentiment                       # demo: score 3 headlines
python -m llm.rag  /path/to/earnings-pdfs     # build an index, sample query
python -m llm.explainer                       # demo: explain one signal
python -m llm.multi_agent                     # demo: routed multi-agent answer
python -m llm.evaluation                      # RAGAS-style scores -> JSON report
```

Everything except the RAG steps works without any PDFs. `evaluation.py` and the
RAG path need an index built first (`build_index` in `rag.py`).

## How it plugs into week2

`explain_signal()` takes a plain dict shaped like `core.strategy.generate_signal()`'s
output, and returns the text for the `Signal.reason` field. week2's Celery task
builds that dict from its `Signal` model and calls this — so `llm/` never
imports Django, and the boundary from week2 stays clean.

## Caches & artifacts (all git-ignored)
- `week3/.cache/sentiment.json` — scored-headline cache
- `week3/.cache/rag_index/` — `vectors.npy` + `chunks.json`
- `evaluation_report.json` — the latest evaluation output

> Concept notes (RAG, embeddings, multi-agent, evaluation): see `../LEARNINGS.md`.
