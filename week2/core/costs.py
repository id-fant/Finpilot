"""The Zerodha equity-delivery (CNC) cost stack — the ONE canonical copy.

WHY this module exists: this arithmetic used to live in four places
(portfolio/views.py, scripts/run_integrated_demo.py,
quant/04_meta_labeling/01_build_dataset.py, week1/one_week_simulation.py),
each with a comment promising it "matches" the others. A promise in a
comment is not a constraint — the moment one copy changes (say SEBI revises
STT), every backtest label, Monte Carlo projection and README number that
reads a stale copy silently disagrees with production. One import, one truth.

week1/one_week_simulation.py deliberately keeps its own copy: it is a
standalone teaching script with no week2 dependency, and its README walks
through the arithmetic line by line. Its copy carries a pointer here.

Charges (Zerodha CNC, both legs unless noted):
  STT    0.1% of turnover          exchange  0.00325%        SEBI  0.0001%
  stamp  0.015% on the BUY leg     GST       18% on exch+SEBI
  DP     ₹13.5 + GST flat per scrip per SELL day (the small-capital killer)

Vectorised: pure arithmetic, so passing NumPy arrays for either leg prices
every simulation in one sweep — the Monte Carlo endpoint relies on this.
"""
from __future__ import annotations


def zerodha_round_trip_cost(buy_value, sell_value):
    """Total cost (₹) of buying `buy_value` and selling `sell_value`.

    Args:
        buy_value: rupee value of the buy leg — float or ndarray.
        sell_value: rupee value of the sell leg — float or ndarray.

    Returns:
        Cost in rupees, same shape as the inputs.
    """
    turnover = buy_value + sell_value
    stt = turnover * 0.001
    exch = turnover * 0.0000325
    sebi = turnover * 0.000001
    stamp = buy_value * 0.00015
    gst = (exch + sebi) * 0.18
    dp = 13.5 * 1.18  # flat per scrip per sell day — dominates small trades
    return stt + exch + sebi + stamp + gst + dp
