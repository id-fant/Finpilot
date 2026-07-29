# FinPilot

**A quant trading assistant for Indian markets (NIFTY 50)** — it generates
daily buy / sell / hold signals, explains them in plain English with an LLM,
and routes the resulting paper (or live) orders to Zerodha.

## About this project

I graduated in mechanical engineering in 2024 and have been teaching myself
software and quantitative finance since. FinPilot is the project I built to
learn both at the same time. I added one layer a week — market-data analysis,
then a Django backend, then an LLM explanation layer, then broker integration,
then a small quant-research track — and tried to do each part properly instead
of just making it run.

A few habits carried over from mechanical engineering more than I expected:
thinking in systems, trusting simulation (the Monte Carlo parts felt familiar
from coursework), and being honest about measurement. A design that "works" on
paper isn't the same as one that survives real-world losses and tolerances —
that idea shows up all over this project, especially in the results below.

This is a learning vehicle and a portfolio piece, **not investment advice.**

## Run it yourself

```bash
git clone … && python run.py --demo
```

One command sets up a virtualenv, applies the database migrations, seeds a
self-contained demo dataset (signals + filled/pending/rejected orders + one
open position), and opens the dashboard at <http://127.0.0.1:5500> in about
30 seconds. No API keys or network required.

![pyrefly](https://img.shields.io/badge/pyrefly-0%20errors-brightgreen)
![pyright](https://img.shields.io/badge/pyright-0%20errors-brightgreen)
![tests](https://img.shields.io/badge/pytest-23%2F23-brightgreen)
&nbsp;_two type-checkers + tests run on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml))._

For a real run (live yfinance prices + LLM-generated explanations):

```bash
python run.py --refresh                # uses your GEMINI_API_KEY from week2/.env
```

## Results — including the bad ones

The strategy was **net negative** over the most recent one-year window
(2025-05 → 2026-05). I'm leaving these numbers up instead of cherry-picking a
flattering window. I read that professional desks throw out most of the
strategies they test, and being willing to show a losing backtest honestly felt
more useful — to me and to anyone reading this — than faking a winner.

**Per-stock RSI strategy** (RSI(14) buy<30 / sell>70, 1-yr window, gross — see
`week1/nifty_comparison.csv` for the raw output):

| Symbol | Gross Return | Sharpe | Max DD |
|--------|-------------:|-------:|-------:|
| RELIANCE.NS | +2.7% | -0.09 | -18.1% |
| WIPRO.NS    | -14.2% | -0.81 | -29.5% |
| ICICIBANK.NS | -11.8% | -0.95 | -18.4% |
| INFY.NS     | -19.6% | -0.96 | -31.8% |
| HDFCBANK.NS | -19.2% | -1.41 | -27.8% |
| TCS.NS      | -27.3% | -1.63 | -32.7% |

**Why they're bad:** the test window caught the 2025 IT-services downturn
(TCS / INFY / WIPRO all fell 14–27%) and the strategy has no trend filter to
step aside in a falling market. The walk-forward and pairs-trading tracks in
`quant/` are what I want to try next — I'll update this table with their
out-of-sample numbers once they've run.

**Why a tiny amount of capital makes it worse, not better:** one round-trip
Zerodha-CNC trade on ₹100 costs ~₹16 in fixed + percentage charges (DP + STT +
exchange + stamp) — a **16% drag per round-trip.** The cost ratio only drops
below 1% above ~₹10k of capital. This was the most surprising thing I learned
on the whole project; more detail below.

### Can I actually trade this with my own money?

**Not yet — and definitely not with ₹100.** Three honest reasons:

1. **The strategy hasn't shown a positive out-of-sample Sharpe** on a
   multi-regime test. I don't want to risk money on something that hasn't even
   beaten buy-and-hold yet.
2. **₹100 is below the cost floor.** Zerodha's per-trade DP charge (₹13.5 + GST)
   is fixed regardless of trade size, so it's a ~14% drag on a ₹100 buy. You'd
   need at least ₹10–50k of working capital before transaction costs stop
   dominating the result.
3. **Paper-trade first.** FinPilot defaults to a paper broker for exactly this
   reason — I'd run it for a few months alongside live markets and compare the
   paper P&L against what real fills would have produced before risking
   anything.

If I wanted production-grade returns I'd need longer backtests, cost-aware
position sizing, regime detection, and proper risk management — each of which
is its own multi-week project. For now this is about learning, not earning.

## What it does

- Generates daily **BUY / SELL / HOLD signals** for NIFTY 50 stocks from a
  3-indicator confluence strategy (RSI, MACD, Bollinger Bands).
- Serves them over a **REST API**, with a Celery job that refreshes signals
  every trading morning.
- Attaches an **LLM-generated explanation** to each signal (Google Gemini),
  grounded in recent news sentiment and earnings-report retrieval (RAG).
- Turns signals into **paper or live orders** via Zerodha Kite (paper is the
  default; live is a one-flag opt-in).
- A **Vite + React dashboard** renders signals, orders, positions and the
  decision journal in either a guided Friendly mode or a dense Terminal mode.
  WebSockets push quote/order changes; a 30-second snapshot is the fallback.
- A **Monte Carlo "Simulation" panel** shows a 1-week probability cone for any
  NIFTY 50 ticker, with Zerodha costs applied — it reports the spread of
  outcomes, not a single misleading point estimate.

## What I learned

The parts I'd actually talk about in an interview:

- **Engineering quality and strategy quality are different things.** I can make
  a system run cleanly and still lose money reliably. Most of my effort went
  into the engineering; the harder, unfinished half is finding a strategy with
  a real edge.
- **Transaction costs dominate at small size.** The ₹100 cost-floor finding
  above reframed how I think about whether a strategy is even worth running.
- **Honest backtesting is mostly about avoiding self-deception** —
  look-ahead bias, testing on one lucky window, and why a backtest that looks
  *too* good usually has a bug.
- **Type safety and CI as a discipline.** I run two Python type-checkers
  (pyrefly + pyright) and a test suite on every push; getting both checkers to
  agree on the same code taught me a lot about how type stubs actually work.
- **Full-stack plumbing** — REST APIs, background jobs, a React dashboard, and
  wiring an LLM into a backend without letting an API outage break the pipeline.

## Tools that ship with the repo

| Command | What it does |
|---|---|
| `python run.py --demo` | One-command try-it: venv + migrations + demo data + dashboard |
| `python run.py --refresh` | Live yfinance fetch + Gemini explanations (needs `GEMINI_API_KEY`) |
| `python week1/one_week_simulation.py` | CLI Monte Carlo on the 1-yr backtest stats + saves a fan-chart PNG |
| `python scripts/run_integrated_demo.py --refresh-db` | Runs the whole pipeline offline in one go: synthetic data → signal engine → paper broker → pairs cointegration → Markowitz weights → Monte Carlo |
| `cd week2 && pytest` | 23 tests covering the engine, API/security contracts, idempotency, quotes, and exactly-once fill reconciliation |

## Tech stack

Python · Django + Django REST Framework · Celery + Redis · PostgreSQL ·
pandas · yfinance · Google Gemini · FAISS · FastAPI · React · Docker · Railway.

## Structure

```
finpilot/
├── week1/             Market-data analysis — indicators, backtests,
│                       one_week_simulation.py (Monte Carlo CLI + fan chart)
├── week2/             Django backend — REST API + Celery automation,
│                       management commands (seed_stocks, seed_demo), tests
├── week3/             LLM layer — sentiment, RAG, multi-agent explainer
├── week4/             Broker integration (Zerodha Kite) + React dashboard
├── quant/             Mean reversion, factor models, portfolio optimisation
├── fastapi_spike/     A small FastAPI port of the returns logic
├── scripts/
│   └── run_integrated_demo.py   Full-pipeline orchestrator
├── docs/              Screenshot + walkthrough notes
├── .github/workflows/ci.yml     Type-checkers + tests on every push
├── run.py · run.ps1             Cross-platform launcher
└── pyrightconfig.json           Shared type-checker config
```

## Manual quick start (without `run.py`)

Each track has its own `requirements.txt`.

```bash
# Week 1 — analysis scripts
cd week1 && pip install -r requirements.txt && python 01_data_foundations.py

# Week 2 — Django backend
cd week2 && pip install -r requirements.txt
copy .env.example .env
python manage.py migrate && python manage.py seed_stocks
python smoke_test.py                  # verify the signal pipeline
python manage.py seed_demo            # populate dashboard demo data
python -m uvicorn finpilot.asgi:application --port 8000

# Week 4 — Vite dashboard (second terminal)
cd ../week4/frontend && npm ci && npm run dev
```

## Production image

The multi-stage image builds the pinned React bundle, installs the Django
runtime, applies migrations, and serves UI + REST + WebSockets on one origin:

```bash
docker build -f week4/Dockerfile -t finpilot .
docker run --rm -p 8000:8000 \
  -e DJANGO_DEBUG=False \
  -e DJANGO_SECRET_KEY=replace-me \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e SECURE_SSL_REDIRECT=False finpilot
```

On this machine Avast re-signs TLS. For a local build only, pass its generated
bundle as an ephemeral BuildKit secret:

```bash
docker build --secret id=ca_bundle,src=.cache/ca_bundle.pem \
  -f week4/Dockerfile -t finpilot .
```

## Market focus

NSE tickers (`.NS` suffix), Indian risk-free rate (~6.5%, the 10-yr G-Sec),
and Zerodha-style costs (~0.13% round-trip + ₹15.93 flat DP charge per scrip
per sell day). NIFTY 50 index is `^NSEI`.

See [`finpilot_master_guide.md`](finpilot_master_guide.md) for the longer
write-up of how the project is put together.
