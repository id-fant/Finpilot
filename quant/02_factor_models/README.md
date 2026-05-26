# Quant — 02: Factor Models

Why did a stock return what it did? A factor model answers that by attributing
returns to a handful of systematic drivers ("factors") plus a leftover. It is
the language of modern quant equity — risk, performance attribution and
smart-beta products are all factor models underneath.

## Scripts (run in order)

| File | What it does |
|------|--------------|
| `01_factor_intro.py` | CAPM — the one-factor (market) baseline; beta and alpha |
| `02_fama_french.py` | builds Market / Momentum / Low-Vol factor portfolios |
| `03_factor_regression.py` | regresses one stock on all three; decomposes its return |

## The thread

1. **CAPM** says one factor — the market — explains a stock's excess return:
   `R - Rf = alpha + beta*(Rm - Rf)`. **Beta** is market sensitivity;
   **alpha** is the unexplained remainder.
2. **Multi-factor** — the market alone leaves a lot unexplained. Fama & French
   added size and value; momentum came later. More factors, less unexplained.
3. **Regression** — regress a stock on the factors. The **loadings** say what
   the stock *is* (a momentum name? a low-vol name?); the **alpha** is what no
   factor explains — and honest alpha is small and rare.

## Honest caveats
- The canonical Fama-French SMB (size) and HML (value) factors need
  fundamental data, and the official factors are US-only. This module builds
  **price-based** factors from an NSE universe instead — same machinery, no
  fundamentals — so the scripts are self-contained and runnable.
- Factor premia are real but **noisy**: a factor can underperform for years
  ("factor winters"). A loading with `|t-stat| > 2` is statistically real;
  below that, treat it as noise.

> Concept notes: see `../../LEARNINGS.md`.
