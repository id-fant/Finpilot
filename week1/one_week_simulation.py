"""One-week trade simulation — what ₹1000 might actually do.

Reads the real backtest output from `nifty_comparison.csv` (the 1-year per-stock
RSI strategy results), derives the implied 1-week return distribution per stock,
and Monte-Carlo-samples 10,000 one-week trades to produce a credible *range* of
outcomes — not a single number.

Apply Zerodha's published equity-delivery cost stack at the end. The output is
deliberately pessimistic about uncertainty (95% CI shown) because point
estimates on a noisy strategy mislead.

Run:  python week1/one_week_simulation.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

CAPITAL = 1000.0
TRADING_DAYS_PER_WEEK = 5
ANNUAL_TRADING_DAYS = 252
WEEKS_PER_YEAR = 52
N_SIMULATIONS = 10_000
SEED = 42  # deterministic run

CSV_PATH = Path(__file__).resolve().parent / "nifty_comparison.csv"
CHART_PATH = Path(__file__).resolve().parent / "one_week_fan_chart.png"


def zerodha_costs(buy_value: float, sell_value: float) -> float:
    """Total round-trip cost for one equity-delivery (CNC) trade on Zerodha."""
    # Brokerage: ₹0 on equity delivery.
    stt = (buy_value + sell_value) * 0.001               # 0.1% per leg
    exch = (buy_value + sell_value) * 0.0000325          # NSE transaction
    sebi = (buy_value + sell_value) * 0.000001           # SEBI charge
    stamp = buy_value * 0.00015                          # stamp duty on buy
    gst = (exch + sebi) * 0.18                           # GST on slice
    dp = 13.5 * 1.18                                     # DP charge per sell day (~₹15.93)
    return stt + exch + sebi + stamp + gst + dp


def monte_carlo_outcome(annual_return_pct: float, annual_sharpe: float,
                        capital: float, n_sims: int, rng: np.random.Generator
                        ) -> dict:
    """Sample n_sims one-week outcomes from the implied distribution.

    Uses the 1-year backtest mean and std to derive 1-week mean / std under
    a normal-returns assumption. Then applies Zerodha costs to every
    sampled outcome. Returns the percentile spread.

    A real strategy has fat tails (rare big moves), so the normal model
    UNDERSTATES tail risk. The 95% CI here is an optimistic lower bound on
    uncertainty — actual losing trades can exceed this.
    """
    annual_return = annual_return_pct / 100
    # Sharpe = (annual_return - rf) / annual_vol  ->  annual_vol = (annual_return - rf) / Sharpe
    # For an Indian risk-free of 6.5% and Sharpe near zero or negative, the
    # algebra is ill-conditioned. Instead, derive annual_vol from observed:
    # if Sharpe is near zero, vol ~ |annual_return|/|Sharpe|, capped at a plausible 30%.
    if abs(annual_sharpe) < 0.01:
        annual_vol = 0.25  # fallback: typical NSE single-name vol
    else:
        rf = 0.065
        annual_vol = abs((annual_return - rf) / annual_sharpe)
        annual_vol = min(max(annual_vol, 0.10), 0.45)  # bracket to a sane range

    weekly_mean = annual_return / WEEKS_PER_YEAR
    weekly_std = annual_vol / np.sqrt(WEEKS_PER_YEAR)

    # Sample n_sims gross weekly returns
    weekly_returns = rng.normal(weekly_mean, weekly_std, n_sims)

    # Apply costs to every outcome
    buy_value = capital
    sell_values = capital * (1 + weekly_returns)
    costs = np.array([zerodha_costs(buy_value, sv) for sv in sell_values])
    net_ends = sell_values - costs
    net_returns = (net_ends - capital) / capital * 100

    return {
        "annual_vol_estimated_pct": round(annual_vol * 100, 1),
        "weekly_mean_pct": round(weekly_mean * 100, 3),
        "weekly_std_pct": round(weekly_std * 100, 3),
        "expected_net_return_pct": round(float(np.mean(net_returns)), 2),
        "expected_net_end_rs": round(float(np.mean(net_ends)), 2),
        "p05_net_end_rs": round(float(np.percentile(net_ends, 5)), 2),   # bad week (5th %ile)
        "p50_net_end_rs": round(float(np.percentile(net_ends, 50)), 2),  # median
        "p95_net_end_rs": round(float(np.percentile(net_ends, 95)), 2),  # good week (95th %ile)
        "prob_profit_pct": round(float(np.mean(net_returns > 0)) * 100, 1),
        "avg_cost_rs": round(float(np.mean(costs)), 2),
    }


def simulate_paths(annual_return_pct: float, annual_sharpe: float,
                   capital: float, n_sims: int, n_steps: int,
                   rng: np.random.Generator) -> np.ndarray:
    """Sample n_sims daily-step price paths over n_steps days.

    Returns an (n_sims, n_steps+1) array where column 0 is the starting capital
    and each subsequent column is the simulated portfolio value at end of day t.
    Used to plot the probability fan — the spread of where capital might land
    each day across all simulated weeks.
    """
    annual_return = annual_return_pct / 100
    rf = 0.065
    if abs(annual_sharpe) < 0.01:
        annual_vol = 0.25
    else:
        annual_vol = abs((annual_return - rf) / annual_sharpe)
        annual_vol = min(max(annual_vol, 0.10), 0.45)

    daily_mean = annual_return / ANNUAL_TRADING_DAYS
    daily_std = annual_vol / np.sqrt(ANNUAL_TRADING_DAYS)

    # Sample (n_sims, n_steps) daily returns -> cumprod -> running capital
    daily_returns = rng.normal(daily_mean, daily_std, (n_sims, n_steps))
    paths = capital * np.cumprod(1 + daily_returns, axis=1)
    # Prepend the starting capital so column 0 is day 0
    return np.column_stack([np.full(n_sims, capital), paths])


def render_fan_chart(per_stock_paths: dict[str, np.ndarray]) -> None:
    """Plot the 5th/50th/95th percentile path per stock — the 'probability cone'.

    A fan chart is the professional way to visualise simulated uncertainty: a
    median line bracketed by widening confidence bands. This replaces the
    *idea* of a 3D price-prediction surface — same information, far more
    legible, and consistent with how risk teams actually communicate.
    """
    # Import matplotlib only when plotting so the script still runs in a
    # headless environment without it (the table output is fully usable alone).
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharey=True)
    axes_flat = axes.flatten()

    days = np.arange(TRADING_DAYS_PER_WEEK + 1)
    for i, (symbol, paths) in enumerate(per_stock_paths.items()):
        ax = axes_flat[i]
        p05 = np.percentile(paths, 5, axis=0)
        p25 = np.percentile(paths, 25, axis=0)
        p50 = np.percentile(paths, 50, axis=0)
        p75 = np.percentile(paths, 75, axis=0)
        p95 = np.percentile(paths, 95, axis=0)

        # Two bands of widening uncertainty (50% and 90% intervals).
        ax.fill_between(days, p05, p95, color="#2563EB", alpha=0.15, label="5-95% range")
        ax.fill_between(days, p25, p75, color="#2563EB", alpha=0.30, label="25-75% range")
        ax.plot(days, p50, color="#1E3A8A", linewidth=2, label="median")
        ax.axhline(CAPITAL, color="#6B7280", linewidth=0.8, linestyle="--",
                   label="starting ₹")

        ax.set_title(symbol, fontsize=10)
        ax.set_xlabel("trading day")
        ax.set_xticks(days)
        ax.grid(alpha=0.3)
        if i == 0:
            ax.set_ylabel(f"capital (₹, from ₹{int(CAPITAL):,})")
            ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    fig.suptitle(
        f"₹{int(CAPITAL):,} Monte Carlo — 1-week probability fan (n={N_SIMULATIONS:,} per stock)",
        fontsize=12, y=0.995,
    )
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  [CHART] fan chart -> {CHART_PATH.name}")


def main() -> None:
    print(f"{'=' * 78}")
    print(f"  ONE-WEEK ₹{int(CAPITAL):,} TRADE SIMULATION — Monte Carlo, n={N_SIMULATIONS:,}")
    print(f"  Source: {CSV_PATH.name} (real 1-yr backtest of RSI strategy)")
    print(f"{'=' * 78}\n")

    if not CSV_PATH.exists():
        print(f"[error] expected {CSV_PATH} — run 01_data_foundations.py first")
        return

    with CSV_PATH.open() as f:
        stocks = list(csv.DictReader(f))

    rng = np.random.default_rng(SEED)

    print(f"  {'Stock':14s}{'Expected':>10s}{'Median':>10s}{'5th %ile':>11s}"
          f"{'95th %ile':>11s}{'P(profit)':>11s}")
    print(f"  {'':14s}{'net %':>10s}{'end ₹':>10s}{'end ₹':>11s}{'end ₹':>11s}"
          f"{'':>11s}")
    print(f"  {'-' * 74}")

    all_outcomes = []
    per_stock_paths: dict[str, np.ndarray] = {}
    for row in stocks:
        outcome = monte_carlo_outcome(
            annual_return_pct=float(row["Total_Return_%"]),
            annual_sharpe=float(row["Sharpe"]),
            capital=CAPITAL, n_sims=N_SIMULATIONS, rng=rng,
        )
        all_outcomes.append(outcome)
        # Daily-step paths for the fan chart. Use a fresh sub-rng so the path
        # samples are independent of the outcome samples (otherwise the table
        # and the chart show coupled — the chart is meant to be a separate view).
        per_stock_paths[row["Symbol"]] = simulate_paths(
            annual_return_pct=float(row["Total_Return_%"]),
            annual_sharpe=float(row["Sharpe"]),
            capital=CAPITAL, n_sims=N_SIMULATIONS,
            n_steps=TRADING_DAYS_PER_WEEK,
            rng=np.random.default_rng(SEED + hash(row["Symbol"]) % 1000),
        )
        print(f"  {row['Symbol']:14s}"
              f"{outcome['expected_net_return_pct']:>9.2f}%"
              f"{outcome['p50_net_end_rs']:>10.2f}"
              f"{outcome['p05_net_end_rs']:>11.2f}"
              f"{outcome['p95_net_end_rs']:>11.2f}"
              f"{outcome['prob_profit_pct']:>10.1f}%")

    # Portfolio = equal weight across all stocks. Diversification reduces vol
    # by ~sqrt(N) IF the holdings are uncorrelated — which they aren't in a
    # single-sector or single-country basket, so the actual reduction is smaller.
    n_stocks = len(stocks)
    avg_expected = np.mean([o['expected_net_return_pct'] for o in all_outcomes])
    avg_p05 = np.mean([o['p05_net_end_rs'] for o in all_outcomes])
    avg_p95 = np.mean([o['p95_net_end_rs'] for o in all_outcomes])
    print(f"  {'-' * 74}")
    print(f"  {'EQ-WT BASKET':14s}{avg_expected:>9.2f}%"
          f"{CAPITAL * (1 + avg_expected / 100):>10.2f}"
          f"{avg_p05:>11.2f}"
          f"{avg_p95:>11.2f}")

    print(f"\n  ASSUMPTIONS (read these before believing the numbers)")
    print(f"  ───────────────────────────────────────────────────────────────")
    print(f"  • Returns sampled from Normal(weekly_mean, weekly_std), derived")
    print(f"    from the 1-yr backtest stats. Real returns have fat tails —")
    print(f"    the 5th-percentile loss UNDERSTATES the worst-case.")
    print(f"  • One round-trip per week (buy Mon, sell Fri). DP charge applies")
    print(f"    once per sell day, regardless of trade size.")
    print(f"  • Past performance is not predictive — the 1-yr window caught")
    print(f"    the IT slump; the next year may differ in either direction.")
    print(f"  • No position sizing, no stop-losses, no regime detection.")
    print(f"  • Equal-weight basket assumes you can buy ₹{int(CAPITAL):,} of EACH stock")
    print(f"    — i.e. ₹{int(CAPITAL) * n_stocks:,} total capital. Real diversification")
    print(f"    requires that capital floor, not the ₹{int(CAPITAL):,} headline.")

    print(f"\n  Bottom line: at ₹{int(CAPITAL):,}, costs are ~{all_outcomes[0]['avg_cost_rs'] / CAPITAL * 100:.2f}% per round-trip.")
    print(f"  A strategy needs to beat that consistently to be worth running.")
    print(f"  These 1-yr backtest numbers do NOT show that edge yet.")

    try:
        render_fan_chart(per_stock_paths)
    except ImportError:
        print("\n  [chart] matplotlib not installed — skipping fan chart render.")


if __name__ == "__main__":
    main()
