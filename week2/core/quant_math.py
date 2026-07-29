"""Reusable quantitative controls for research and live execution.

All functions are framework-free and deterministic.  They deliberately return
``None`` when a statistic cannot be estimated safely so callers can fail open
instead of manufacturing confidence from too little data.
"""
from __future__ import annotations

from itertools import combinations
from math import e, log, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd


def expected_trade_return(
    probability: float,
    average_win: float,
    average_loss: float,
    cost_rate: float = 0.0,
) -> float:
    """Expected net return per unit of capital.

    ``average_win`` and ``average_loss`` are positive decimal returns.  Costs
    are charged regardless of outcome, matching a round-trip trade.
    """
    p = float(np.clip(probability, 0.0, 1.0))
    win = max(float(average_win), 0.0)
    loss = max(float(average_loss), 0.0)
    return p * win - (1.0 - p) * loss - max(float(cost_rate), 0.0)


def ewma_annualized_volatility(
    returns: pd.Series,
    halflife: int = 20,
    periods_per_year: int = 252,
) -> float | None:
    """Latest exponentially weighted annualized volatility."""
    clean = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan)
    clean = clean.dropna()
    if len(clean) < max(5, halflife // 2):
        return None
    variance = clean.ewm(halflife=halflife, adjust=False).var(bias=False).iloc[-1]
    if not np.isfinite(variance) or variance < 0:
        return None
    return float(sqrt(variance * periods_per_year))


def volatility_target_fraction(
    current_volatility: float | None,
    target_volatility: float = 0.15,
    max_fraction: float = 1.0,
) -> float:
    """Capital fraction required to target volatility, without leverage."""
    if current_volatility is None or not np.isfinite(current_volatility):
        return float(max_fraction)
    if current_volatility <= 0:
        return float(max_fraction)
    return float(np.clip(target_volatility / current_volatility, 0.0, max_fraction))


def trend_regime(
    close: pd.Series,
    benchmark_close: pd.Series | None = None,
    fast_window: int = 50,
    slow_window: int = 200,
    slope_window: int = 20,
) -> dict:
    """Classify an asset's long-term trend and optional relative momentum.

    A BUY is eligible when price is above its slow average, the fast average
    is above the slow average, and the slow average is rising.  If a benchmark
    is supplied, non-negative relative momentum is also required.
    """
    prices = pd.Series(close, dtype=float).dropna()
    required = slow_window + slope_window
    if len(prices) < required:
        return {
            "eligible": None,
            "label": "unknown",
            "score": None,
            "relative_momentum": None,
        }

    fast = prices.rolling(fast_window).mean()
    slow = prices.rolling(slow_window).mean()
    slow_now = float(slow.iloc[-1])
    slow_then = float(slow.iloc[-1 - slope_window])
    asset_momentum = float(prices.iloc[-1] / prices.iloc[-1 - fast_window] - 1)

    relative_momentum: float | None = None
    relative_ok = True
    if benchmark_close is not None:
        bench = pd.Series(benchmark_close, dtype=float).dropna()
        if len(bench) >= fast_window + 1:
            bench_momentum = float(bench.iloc[-1] / bench.iloc[-1 - fast_window] - 1)
            relative_momentum = asset_momentum - bench_momentum
            relative_ok = relative_momentum >= 0

    checks = [
        float(prices.iloc[-1]) > slow_now,
        float(fast.iloc[-1]) > slow_now,
        slow_now > slow_then,
        relative_ok,
    ]
    score = sum(checks) / len(checks)
    eligible = all(checks)
    return {
        "eligible": eligible,
        "label": "bullish" if eligible else "bearish",
        "score": round(float(score), 4),
        "relative_momentum": (
            None if relative_momentum is None else round(relative_momentum, 6)
        ),
    }


def fractional_kelly(
    probability: float,
    average_win: float,
    average_loss: float,
    fraction: float = 0.25,
    max_fraction: float = 0.05,
) -> float:
    """Conservative Kelly capital fraction, clipped to long-only bounds."""
    win = float(average_win)
    loss = float(average_loss)
    if win <= 0 or loss <= 0:
        return 0.0
    p = float(np.clip(probability, 0.0, 1.0))
    payoff_ratio = win / loss
    full_kelly = p - (1.0 - p) / payoff_ratio
    return float(np.clip(full_kelly * fraction, 0.0, max_fraction))


def equal_risk_contribution_weights(
    covariance: np.ndarray,
    tolerance: float = 1e-10,
    max_iterations: int = 10_000,
) -> np.ndarray:
    """Long-only equal-risk-contribution weights via multiplicative updates."""
    cov = np.asarray(covariance, dtype=float)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1] or cov.shape[0] == 0:
        raise ValueError("covariance must be a non-empty square matrix")
    if not np.isfinite(cov).all():
        raise ValueError("covariance contains non-finite values")

    n_assets = cov.shape[0]
    weights = np.full(n_assets, 1.0 / n_assets)
    target = 1.0 / n_assets
    for _ in range(max_iterations):
        previous = weights.copy()
        portfolio_variance = float(weights @ cov @ weights)
        if portfolio_variance <= 0:
            return np.full(n_assets, 1.0 / n_assets)
        for i in range(n_assets):
            diagonal = cov[i, i]
            if diagonal <= 0:
                continue
            cross = float(cov[i] @ weights - diagonal * weights[i])
            discriminant = cross * cross + 4 * diagonal * target * portfolio_variance
            weights[i] = max(
                (-cross + sqrt(max(discriminant, 0.0))) / (2 * diagonal),
                1e-12,
            )
        if float(np.max(np.abs(weights - previous))) < tolerance:
            break
    return weights / weights.sum()


def mean_reversion_half_life(spread: pd.Series) -> float | None:
    """Estimate Ornstein-Uhlenbeck half-life from an AR(1) regression."""
    values = pd.Series(spread, dtype=float).replace([np.inf, -np.inf], np.nan)
    lagged = values.shift(1)
    delta = values.diff()
    aligned = pd.concat([delta, lagged], axis=1).dropna()
    if len(aligned) < 20:
        return None
    x = aligned.iloc[:, 1].to_numpy()
    y = aligned.iloc[:, 0].to_numpy()
    slope = float(np.linalg.lstsq(
        np.column_stack([np.ones(len(x)), x]), y, rcond=None
    )[0][1])
    if not np.isfinite(slope) or slope >= 0:
        return None
    half_life = -log(2.0) / slope
    return float(half_life) if np.isfinite(half_life) and half_life > 0 else None


def kalman_hedge_ratio(
    dependent: pd.Series,
    independent: pd.Series,
    process_variance: float = 1e-5,
    observation_variance: float = 1e-3,
) -> pd.Series:
    """Estimate a time-varying zero-intercept hedge ratio."""
    y, x = pd.Series(dependent, dtype=float).align(
        pd.Series(independent, dtype=float), join="inner"
    )
    beta = 0.0
    variance = 1.0
    estimates: list[float] = []
    for y_value, x_value in zip(y.to_numpy(), x.to_numpy()):
        if not np.isfinite(y_value) or not np.isfinite(x_value):
            estimates.append(beta)
            continue
        predicted_variance = variance + process_variance
        innovation_variance = (
            x_value * x_value * predicted_variance + observation_variance
        )
        gain = predicted_variance * x_value / innovation_variance
        beta += gain * (y_value - beta * x_value)
        variance = max((1.0 - gain * x_value) * predicted_variance, 1e-12)
        estimates.append(beta)
    return pd.Series(estimates, index=y.index, name="hedge_ratio")


def _sharpe(returns: np.ndarray) -> float:
    clean = returns[np.isfinite(returns)]
    if len(clean) < 2:
        return 0.0
    std = float(np.std(clean, ddof=1))
    return float(np.mean(clean) / std) if std > 0 else 0.0


def deflated_sharpe_ratio(
    returns: pd.Series | np.ndarray,
    trial_sharpes: list[float] | np.ndarray,
    periods_per_year: int = 252,
) -> dict:
    """Probability that an observed Sharpe exceeds selection bias.

    The benchmark is the expected maximum Sharpe across the tested variants;
    skewness and kurtosis adjust the probabilistic Sharpe denominator.
    """
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 3:
        return {"probability": None, "sharpe": None, "benchmark_sharpe": None}
    observed = _sharpe(values)
    trials = np.asarray(trial_sharpes, dtype=float)
    trials = trials[np.isfinite(trials)]
    if len(trials) <= 1:
        benchmark = 0.0
    else:
        trial_std = float(np.std(trials, ddof=1))
        n_trials = len(trials)
        normal = NormalDist()
        gamma = 0.5772156649015329
        benchmark = trial_std * (
            (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / n_trials)
            + gamma * normal.inv_cdf(1.0 - 1.0 / (n_trials * e))
        )
    centered = values - float(values.mean())
    sigma = float(values.std(ddof=0))
    skew = float(np.mean(centered**3) / sigma**3) if sigma > 0 else 0.0
    kurtosis = float(np.mean(centered**4) / sigma**4) if sigma > 0 else 3.0
    denominator = sqrt(max(
        1.0 - skew * observed + ((kurtosis - 1.0) / 4.0) * observed**2,
        1e-12,
    ))
    statistic = (observed - benchmark) * sqrt(len(values) - 1) / denominator
    probability = NormalDist().cdf(statistic)
    annualizer = sqrt(periods_per_year)
    return {
        "probability": float(probability),
        "sharpe": float(observed * annualizer),
        "benchmark_sharpe": float(benchmark * annualizer),
    }


def probability_of_backtest_overfitting(
    performance_matrix: pd.DataFrame | np.ndarray,
    partitions: int = 8,
) -> dict:
    """Estimate PBO with combinatorially symmetric cross-validation (CSCV)."""
    matrix = np.asarray(performance_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return {"probability": None, "splits": 0}
    partitions = min(int(partitions), matrix.shape[0])
    if partitions < 4:
        return {"probability": None, "splits": 0}
    if partitions % 2:
        partitions -= 1
    groups = np.array_split(np.arange(matrix.shape[0]), partitions)
    lambdas: list[float] = []
    for chosen in combinations(range(partitions), partitions // 2):
        in_idx = np.concatenate([groups[i] for i in chosen])
        out_idx = np.concatenate([
            groups[i] for i in range(partitions) if i not in chosen
        ])
        in_sharpes = np.array([_sharpe(matrix[in_idx, j])
                                for j in range(matrix.shape[1])])
        selected = int(np.argmax(in_sharpes))
        out_sharpes = np.array([_sharpe(matrix[out_idx, j])
                                 for j in range(matrix.shape[1])])
        rank = float(
            (np.sum(out_sharpes < out_sharpes[selected]) + 0.5)
            / matrix.shape[1]
        )
        rank = float(np.clip(rank, 1e-9, 1.0 - 1e-9))
        lambdas.append(log(rank / (1.0 - rank)))
    return {
        "probability": float(np.mean(np.asarray(lambdas) <= 0.0)),
        "splits": len(lambdas),
    }
