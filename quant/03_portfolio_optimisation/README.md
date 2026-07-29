# Quant — 03: Portfolio Optimisation

Picking good stocks is half the job. The other half is *how much* of each to
hold. Portfolio optimisation answers that — and its central insight is that a
portfolio's risk is not the average of its parts, it is their **covariance**.

## Scripts (run in order)

| File | What it does |
|------|--------------|
| `01_markowitz.py` | draws the efficient frontier from 20,000 random portfolios |
| `02_sharpe_maximisation.py` | Ledoit-Wolf covariance, max-Sharpe and equal-risk-contribution weights |

## The thread

1. **Markowitz / the efficient frontier** — combining assets that don't move
   together lowers risk for free (diversification, the one "free lunch"). For
   every risk level there is a best-possible return; that set of best
   portfolios is the efficient frontier. `01` finds it by brute-force random
   sampling.
2. **Maximising Sharpe** — sampling only gets *close* to the best portfolio.
   `02` solves for it exactly with a constrained optimiser (SciPy SLSQP). The
   answer is the **tangency portfolio** — the highest risk-adjusted return
   available from the basket.

## Robust live weights

`02` also reports an equal-risk-contribution portfolio. Ledoit-Wolf shrinkage
stabilizes noisy correlations, while risk parity avoids relying entirely on
fragile expected-return estimates.

## The honest caveat
Optimisation is fitted to the **past**. Expected returns are notoriously hard
to estimate, and the optimiser happily pours weight into whatever looked best
in-sample. That is why a naive **equal-weight** portfolio is so stubbornly hard
to beat out-of-sample — and why both scripts compare against it.

> Concept notes: see `../../LEARNINGS.md`.
