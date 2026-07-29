# Quant — 01: Mean Reversion

Trend-following bets a move *continues*. Mean reversion bets it *reverses* —
that a series pulled away from its average is dragged back. The catch: this
only works on a series that **has** a stable average. Most price series do not.

## Scripts (run in order)

| File | What it does |
|------|--------------|
| `01_stationarity.py` | ADF test — proves prices wander but returns/spreads don't |
| `02_cointegration.py` | Engle-Granger test — finds pairs of stocks tied together |
| `03_pairs_trading.py` | Kalman hedge ratio and half-life-adaptive z-score backtest |

## The thread

1. **Stationarity** — a stationary series has a constant mean and variance, so
   "it will revert" is a meaningful statement. Prices are *non-stationary*
   (a random walk); returns are stationary. So you never mean-revert a price.
2. **Cointegration** — two prices can each wander, yet their *spread* stays
   stationary. Such a pair is cointegrated, and the spread is tradeable.
3. **Pairs trading** — go long the cheap leg and short the rich leg whenever
   the spread's z-score is extreme; close when it reverts. Market-neutral: the
   bet is on convergence, not market direction.

The trading script updates its hedge ratio through a Kalman filter and derives
the z-score lookback from the spread's estimated mean-reversion half-life.

## Watch out for
- **Correlation ≠ cointegration.** Correlation is about co-movement of returns;
  cointegration is about prices not drifting apart. Pairs trading needs the
  second.
- **Regime change.** A cointegrating relationship can break (a merger, a
  sector shock). When it does, the spread stops reverting and the strategy
  bleeds. Re-test cointegration regularly.

> Concept notes: see `../../LEARNINGS.md`.
