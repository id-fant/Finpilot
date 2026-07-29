from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.quant_math import (
    deflated_sharpe_ratio,
    equal_risk_contribution_weights,
    expected_trade_return,
    fractional_kelly,
    kalman_hedge_ratio,
    mean_reversion_half_life,
    probability_of_backtest_overfitting,
    trend_regime,
    volatility_target_fraction,
)


def test_expected_value_includes_round_trip_costs():
    assert expected_trade_return(0.5, 0.04, 0.02, 0.001) == pytest.approx(0.009)
    assert expected_trade_return(0.3, 0.02, 0.02, 0.001) < 0


def test_fractional_kelly_is_long_only_and_capped():
    assert fractional_kelly(0.5, 0.04, 0.02) == 0.05
    assert fractional_kelly(0.2, 0.02, 0.04) == 0.0


def test_volatility_target_does_not_add_leverage():
    assert volatility_target_fraction(0.30, 0.15) == 0.5
    assert volatility_target_fraction(0.05, 0.15) == 1.0
    assert volatility_target_fraction(None, 0.15) == 1.0


def test_trend_regime_requires_history_then_classifies():
    short = pd.Series(np.arange(100.0))
    assert trend_regime(short)["eligible"] is None
    rising = pd.Series(np.linspace(100.0, 200.0, 260))
    result = trend_regime(rising)
    assert result["eligible"] is True
    assert result["label"] == "bullish"


def test_equal_risk_contribution_balances_risk():
    covariance = np.array([[0.04, 0.0], [0.0, 0.01]])
    weights = equal_risk_contribution_weights(covariance)
    contributions = weights * (covariance @ weights)
    shares = contributions / contributions.sum()
    np.testing.assert_allclose(weights.sum(), 1.0, atol=1e-10)
    np.testing.assert_allclose(shares, [0.5, 0.5], atol=1e-5)


def test_half_life_and_kalman_ratio_on_synthetic_series():
    rng = np.random.default_rng(7)
    spread = [0.0]
    for shock in rng.normal(0, 0.2, 400):
        spread.append(0.85 * spread[-1] + shock)
    half_life = mean_reversion_half_life(pd.Series(spread))
    assert half_life is not None
    assert 2.0 < half_life < 8.0

    x = pd.Series(np.linspace(10.0, 100.0, 300))
    y = 1.7 * x
    beta = kalman_hedge_ratio(y, x)
    assert abs(beta.iloc[-1] - 1.7) < 0.01


def test_backtest_diagnostics_are_bounded():
    rng = np.random.default_rng(11)
    returns = rng.normal(0.001, 0.01, 300)
    result = deflated_sharpe_ratio(
        returns, [0.01, 0.03, 0.05, 0.08]
    )
    assert result["probability"] is not None
    assert 0 <= result["probability"] <= 1

    matrix = rng.normal(0.0, 0.01, (240, 5))
    pbo = probability_of_backtest_overfitting(matrix)
    assert pbo["splits"] == 70
    assert 0 <= pbo["probability"] <= 1
