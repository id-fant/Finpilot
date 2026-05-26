# FinPilot — Master Guide

The one document that explains *what* FinPilot is, *why* each piece exists, and
*how* the tracks connect. Read this first; every folder has its own README for
the detail. The authoritative build plan is `finpilot_claude_code_spec.md`.

---

## 1. The idea

FinPilot is an AI-powered quantitative trading assistant for the Indian market
(NIFTY 50). It fetches market data, computes technical signals, explains them
in plain English with an LLM layer, and can route the resulting orders to a
broker.

It is also a **learning vehicle and portfolio project** — built to land a
remote AI/fintech engineering role. It is constructed in weekly tracks, each a
deliberate step up in scope, plus a parallel **quant track** for research
depth and a **FastAPI spike** as a focused application artifact.

---

## 2. The build, week by week

### Week 1 — Technical-analysis foundation (`week1/`) — DONE
OHLCV data, returns, Sharpe, drawdown; RSI / MACD / Bollinger Bands; a
`vectorbt` backtest with walk-forward validation. **Output:** a strategy that
turns prices into signals, with the overfitting traps understood.

### Week 2 — Django backend (`week2/`) — DONE
The Week 1 logic rebuilt as a service. A framework-free strategy **engine**
(`core/`), `Stock` / `Signal` / `Position` / `Order` models, a DRF REST API,
and a Celery task (`generate_daily_signals`) that refreshes signals every
trading morning. **Output:** signals on tap via HTTP, generated automatically.

### Week 3 — LLM layer (`week3/`) — PLANNED
Every signal gets an AI-generated, plain-English explanation grounded in real
data: news-sentiment scoring (Gemini), a RAG pipeline over earnings PDFs
(FAISS), a multi-agent explainer, and a RAGAS evaluation harness.
**Output:** signals you can *understand*, not just *see*.

### Week 4 — Broker integration + cloud deploy (`week4/`) — DONE (deploy pending)
The last mile — turning a *signal* into an *order*. `PaperBroker` (simulated,
the safe default) and `KiteClient` (live Zerodha) share one interface;
`OrderManager` sizes and risk-checks orders and routes them. A static
dashboard frontend; `Dockerfile` / `railway.toml` for a Railway deploy.

---

## 3. The quant track (`quant/`)

The research track that runs alongside the weekly build — strategy *depth*,
the part that differentiates a quant from a backend developer.

- **`01_mean_reversion/`** — stationarity (ADF), cointegration (Engle-Granger),
  a z-score pairs-trading strategy. The flagship interview demo.
- **`02_factor_models/`** — CAPM, a multi-factor model, return decomposition.
- **`03_portfolio_optimisation/`** — the Markowitz frontier, max-Sharpe weights.

---

## 4. The FastAPI spike (`fastapi_spike/`)

A small, self-contained FastAPI service — a "Returns Assistant" exposing the
return/risk metrics as a typed JSON API. Two purposes: prove the strategy logic
ports cleanly out of Django (ports-and-adapters), and serve as a focused
portfolio piece for FastAPI-oriented job applications.

---

## 5. How the pieces connect

```
   prices ──► core/ strategy engine ──► signals
                      │
                      ▼
   week2 Django API + Celery  ──►  signals served + auto-refreshed
                      │
                      ▼
   week3 LLM layer ──► each signal gets a plain-English, grounded explanation
                      │
                      ▼
   week4 order_manager ──► paper_trade  (default, safe)
                       └─► kite_client  (live, opt-in)
                      │
                      ▼
              week4 frontend dashboard  +  Railway deploy

   quant/         — independent research track; good ideas graduate into core/
   fastapi_spike/ — independent re-packaging of the metrics logic
```

The recurring design idea: **keep the core strategy engine free of any
framework**, so it can be served by Django *or* FastAPI, and traded through a
paper broker *or* a live one, without rewrites.

---

## 6. Repository conventions

- **Commits** — Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`,
  `test:`, `chore:`).
- **Build order** — Week 1 → 2 → 3 → 4 → Quant → FastAPI; confirm a week works
  before starting the next.
- **Secrets** — always in a git-ignored `.env`, never in code.
- **`_archive/`** — the earlier project iteration, kept locally, git-ignored.
- **Comments are learning material** — every file explains the *why*, with
  `# WHY:` notes and `INTERVIEW:` cues.

---

## 7. Setup at a glance

| Track | Setup |
|-------|-------|
| `week1` | `pip install -r week1/requirements.txt` |
| `week2` | Django project — see `week2/README.md` |
| `week3` | LLM layer — see `week3/README.md` (when built) |
| `week4` | broker demos + Railway deploy — see `week4/README.md` |
| `quant` | `pip install -r quant/requirements.txt` |
| `fastapi_spike` | `pip install -r fastapi_spike/requirements.txt`; `uvicorn` |

Concept notes and interview lines live in `LEARNINGS.md` (git-ignored).
