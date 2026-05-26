# FinPilot — Quant Track

The research track that runs alongside the weekly engineering build. The weeks
teach how to *ship* a strategy; this teaches strategy *depth* — the part that
separates a quant from a backend developer who happens to touch finance.

## Modules

| Folder | Topic | Core idea |
|--------|-------|-----------|
| `01_mean_reversion/` | stationarity → cointegration → pairs trading | trade a stationary spread, market-neutral |
| `02_factor_models/` | CAPM → multi-factor model → return decomposition | explain returns by systematic factors |
| `03_portfolio_optimisation/` | efficient frontier → max-Sharpe weights | how to *weight* a basket, not just pick it |

Each folder has its own README and numbered, runnable scripts — run them in
order; later scripts build on earlier ideas.

## Setup

```bash
cd quant
pip install -r requirements.txt
```

Then run any script from inside its folder:

```bash
cd 01_mean_reversion
python 01_stationarity.py
```

Every script fetches NSE data live via yfinance and saves a `.png` chart next
to itself.

## New dependencies (vs. the earlier weeks)
- **`statsmodels`** — the ADF test, the cointegration test, OLS regressions.
- **`scipy`** — the constrained optimiser used to solve for max-Sharpe weights.

## How this connects to the rest of FinPilot
These are research notebooks-as-scripts: they prototype *ideas*. A promising
one (a robust factor, a stable pair) graduates into the week_1 strategy engine,
which the week_2 service then runs and the week4 broker can trade.

> Concept notes and interview lines: see `../LEARNINGS.md`.
