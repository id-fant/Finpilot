# FinPilot

**An AI-powered quant trading assistant for Indian markets (NIFTY 50)** —
generates daily signals, explains them in plain English with an LLM, and routes
the resulting paper or live orders to Zerodha.

<!--
  ── TOP-OF-FOLD SLOTS — fill these in once available ─────────────────────────
  Goal: a recruiter scanning for 60 seconds should leave knowing what it does,
  see it working (Loom), see honest numbers (results table), and have a link.

  [ ] Loom (90-sec walkthrough): replace the placeholder block below
  [ ] Live URL (after Railway deploy): replace the badge below
  [ ] Results table: fill in once `quant/` + `week1/` backtests have run
-->

🎬 **Demo:** _90-second walkthrough — `<add Loom URL>` once recorded._

🌐 **Live demo:** ![status](https://img.shields.io/badge/live-not%20yet%20deployed-lightgrey)
&nbsp;&nbsp;_`<add Railway URL>` once deployed._

🔒 **Type-checked twice:** ![pyrefly](https://img.shields.io/badge/pyrefly-0%20errors-brightgreen)
![pyright](https://img.shields.io/badge/pyright-0%20errors-brightgreen)
&nbsp;&nbsp;![tests](https://img.shields.io/badge/pytest-8%2F8-brightgreen)
&nbsp;&nbsp;_every push gated by GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml))._

## Try it locally in one command

```bash
python run.py --demo
```

Sets up a virtualenv, applies migrations, seeds a self-contained demo dataset
(signals + filled/pending/rejected orders + one open position), and opens the
Cardinal dashboard at <http://127.0.0.1:5500>. No API keys or network required.

For a real run (live yfinance prices, LLM-generated explanations):

```bash
python run.py --refresh                # uses your GEMINI_API_KEY from week2/.env
```

## Results — honest, including the bad ones

The current strategy was **net negative** over the most recent 1-year window
(2025-05 → 2026-05). I'm leaving these numbers up rather than cherry-picking a
flattering window, because the point of the project is to demonstrate honest
evaluation — hedge funds discard 99 strategies for every 1 deployed, and the
willingness to *publish* a losing backtest is the differentiator.

**Per-stock RSI strategy** (RSI(14) buy<30 / sell>70, 1-yr window, gross, see
`week1/nifty_comparison.csv` for the raw output):

| Symbol | Gross Return | Sharpe | Max DD |
|--------|-------------:|-------:|-------:|
| RELIANCE.NS | +2.7% | -0.09 | -18.1% |
| WIPRO.NS    | -14.2% | -0.81 | -29.5% |
| ICICIBANK.NS | -11.8% | -0.95 | -18.4% |
| INFY.NS     | -19.6% | -0.96 | -31.8% |
| HDFCBANK.NS | -19.2% | -1.41 | -27.8% |
| TCS.NS      | -27.3% | -1.63 | -32.7% |

**Why these are bad:** the test window caught the 2025 IT-services downturn
(TCS / INFY / WIPRO all -14% to -27%) and the strategy doesn't have a
trend-filter to step aside. The walk-forward and pairs-trading tracks
(`quant/`) are the next planned attempts — the README will update with their
real OOS numbers as they run.

**Why ₹100 of capital makes this worse, not better:** a one-round-trip
Zerodha-CNC trade on ₹100 incurs ~₹16 in DP + STT + exchange + stamp charges
— **16% fixed-cost drag per round-trip.** The cost ratio falls below 1% only
above ~₹10k of capital. See [§ Can I trade this with my own money?](#can-i-trade-this-with-my-own-money) below.

### Can I trade this with my own money?

**No, not yet — and not with ₹100.** Three honest reasons:

1. **The strategy hasn't shown positive OOS Sharpe** on a multi-regime test.
   Don't risk capital on a strategy that hasn't beaten buy-and-hold yet.
2. **₹100 is below the cost-floor.** Zerodha's per-trade DP charge (₹13.5 + GST)
   is fixed regardless of trade size, so it's a ~14% drag on a ₹100 buy. You
   need at least ₹10–50k of working capital before transaction costs stop
   dominating.
3. **Paper-trade first.** FinPilot defaults to `PaperBroker` for a reason —
   run it for 3+ months alongside live markets and compare paper P&L vs. what
   real fills would have produced. Then revisit.

This project is built as a **portfolio piece and a learning vehicle**, not
investment advice. If you want production-grade returns, you need (a) longer
backtests, (b) cost-aware position sizing, (c) regime detection, and (d)
proper risk management — each of which is its own multi-week project.

## What it does

- Generates daily **BUY / SELL / HOLD signals** for NIFTY 50 stocks from a
  3-indicator confluence strategy (RSI, MACD, Bollinger Bands).
- Serves them over a **REST API**, with a Celery job that refreshes signals
  every trading morning.
- Attaches an **LLM-generated explanation** to each signal (Gemini), grounded
  in real news sentiment and earnings-call RAG over quarterly reports.
- Turns signals into **paper or live orders** via Zerodha Kite (paper is the
  default; live is a one-flag opt-in).
- A **Cardinal React dashboard** renders signals, the order book, and open
  positions — all auto-refreshing every 30 s.
- A **Monte Carlo "Simulation" panel** on the dashboard shows a 1-week
  probability cone for any NIFTY 50 ticker, with Zerodha CNC costs applied
  and the percentile spread reported honestly — not a point estimate.

## Tools that ship with the repo

| Command | What it does |
|---|---|
| `python run.py --demo` | One-command try-it: venv + migrations + demo data + dashboard |
| `python run.py --refresh` | Live yfinance fetch + Gemini explanations (needs `GEMINI_API_KEY`) |
| `python week1/one_week_simulation.py` | CLI Monte Carlo on the 1-yr backtest stats + saves a fan chart PNG |
| `python scripts/run_integrated_demo.py --refresh-db` | End-to-end orchestrator: synthetic data → signal engine → paper broker → pairs cointegration → Markowitz tangency → Monte Carlo, all in one run, fully offline |
| `cd week2 && pytest` | 8/8 tests covering the framework-free engine + seed_demo idempotency + serializer contract |

## Tech stack

Python · Django + Django REST Framework · Celery + Redis · PostgreSQL ·
pandas · yfinance · Google Gemini · FAISS · FastAPI · React · Docker · Railway.

## Structure

```
finpilot/
├── week1/             Technical-analysis foundation — indicators, backtests,
│                       one_week_simulation.py (Monte Carlo CLI + fan chart)
├── week2/             Django backend — REST API + Celery signal automation,
│                       management commands (seed_stocks, seed_demo), pytest suite
├── week3/             LLM layer — sentiment, RAG, multi-agent explainer
├── week4/             Broker integration (Zerodha Kite) + Cardinal React dashboard
│                       (Dashboard · Markets · Portfolio · Trades · Simulation · …)
├── quant/             Mean reversion, factor models, portfolio optimisation
├── fastapi_spike/     FastAPI port of the returns logic
├── scripts/
│   └── run_integrated_demo.py  Full-pipeline orchestrator
├── docs/
│   ├── SCREENSHOTS.md          Capture sequence + 90-sec Loom script
│   └── screenshots/            (PNGs land here)
├── .github/workflows/ci.yml    Two-checker CI + pytest + smoke test
├── run.py · run.ps1            Unified launcher (cross-platform)
└── pyrightconfig.json          Shared type-checker config (pyrefly + pyright)
```

Several personal-workflow files are kept out of the public repo via
`.gitignore` — process notes, study material, and similar artefacts that
aren't part of the deliverable.

## Manual quick start (without `run.py`)

Each track has its own `requirements.txt` and `README.md`.

```bash
# Week 1 — analysis scripts
cd week1 && pip install -r requirements.txt && python 01_data_foundations.py

# Week 2 — Django backend
cd week2 && pip install -r requirements.txt
copy .env.example .env
python manage.py migrate && python manage.py seed_stocks
python smoke_test.py                  # verify the signal pipeline
python manage.py seed_demo            # populate dashboard demo data
python manage.py runserver
```

## Market focus

NSE tickers (`.NS` suffix), Indian risk-free rate (~6.5%, the 10-yr G-Sec),
Zerodha-style costs (~0.13% round-trip + ₹15.93 flat DP charge per scrip per
sell day). NIFTY 50 index is `^NSEI`.

See [`finpilot_master_guide.md`](finpilot_master_guide.md) for the full
architecture narrative and the build sequence.
