"""FinPilot — FastAPI "Returns Assistant".

A small, self-contained FastAPI service: give it an NSE ticker and it returns
the headline return/risk metrics — total return, CAGR, volatility, Sharpe,
max drawdown. It is the week_1 analysis logic, re-packaged as a clean JSON API.

Why this spike exists:
  - it proves the metric logic ports out of Django cleanly (ports & adapters —
    pure functions, no framework lock-in);
  - it is a tight, reviewable portfolio piece for a job application: a focused
    FastAPI service, not a sprawling framework project.

Run (from the fastapi_spike/ folder):
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    open http://127.0.0.1:8000/docs      # interactive, auto-generated
"""
from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query

from app.models import (
    CompareRequest, CompareResponse, HealthResponse, StockMetrics,
)

RISK_FREE_RATE = 0.065  # Indian 10-yr G-Sec
TRADING_DAYS = 252

app = FastAPI(
    title="FinPilot — Returns Assistant",
    description="Return and risk metrics for NSE stocks. A FastAPI re-packaging "
                "of the FinPilot week_1 analysis logic.",
    version="0.1.0",
)


# ── Core logic (pure, framework-free — this is the part that "ports") ────────

def fetch_close(symbol: str, period: str) -> pd.Series:
    """Daily Close for one ticker. Raises RuntimeError on an empty response."""
    df = yf.Ticker(symbol).history(period=period)
    if df.empty:
        raise RuntimeError(f"no price data for '{symbol}'")
    # pandas stubs union `df[col]` as `Series | DataFrame`; single string key
    # is always Series at runtime. Pin it so the return type is clean.
    close = cast("pd.Series", df["Close"])  # pyrefly: ignore[redundant-cast]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close


def compute_metrics(symbol: str, period: str) -> StockMetrics:
    """Fetch a stock and compute its return/risk metrics."""
    close = fetch_close(symbol, period)
    returns = close.pct_change().dropna()
    if len(returns) < 2:
        raise RuntimeError(f"not enough history for '{symbol}'")

    total = close.iloc[-1] / close.iloc[0] - 1
    years = len(returns) / TRADING_DAYS
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else 0.0

    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    ann_return = returns.mean() * TRADING_DAYS
    sharpe = (ann_return - RISK_FREE_RATE) / ann_vol if ann_vol else 0.0

    wealth = (1 + returns).cumprod()
    max_dd = ((wealth - wealth.cummax()) / wealth.cummax()).min()

    return StockMetrics(
        symbol=symbol.upper(),
        # `Index.__getitem__` returns `Index | scalar`; for a DatetimeIndex
        # the scalar is always a Timestamp with `.date()`. Wrap to coerce.
        start_date=str(pd.Timestamp(close.index[0]).date()),  # pyright: ignore[reportArgumentType]
        end_date=str(pd.Timestamp(close.index[-1]).date()),  # pyright: ignore[reportArgumentType]
        trading_days=len(returns),
        total_return_pct=round(float(total) * 100, 2),
        annualised_return_pct=round(float(cagr) * 100, 2),
        annualised_volatility_pct=round(float(ann_vol) * 100, 2),
        sharpe_ratio=round(float(sharpe), 3),
        # pyrefly sees max_dd as float already; pyright sees `Series | float`
        # — the float() pin is needed for pyright. Same checker-disagreement
        # pattern as week2/core/strategy.py _clean().
        # pyrefly: ignore[unnecessary-type-conversion]
        max_drawdown_pct=round(float(max_dd) * 100, 2),
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    """Liveness check."""
    return HealthResponse(status="ok", service="returns-assistant")


@app.get("/metrics/{symbol}", response_model=StockMetrics, tags=["metrics"])
def get_metrics(
    symbol: str,
    period: str = Query("1y", description="yfinance period: 6mo / 1y / 2y / 5y"),
) -> StockMetrics:
    """Return/risk metrics for one stock.

    Example:  GET /metrics/RELIANCE.NS?period=2y
    """
    try:
        return compute_metrics(symbol, period)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/compare", response_model=CompareResponse, tags=["metrics"])
def compare(request: CompareRequest) -> CompareResponse:
    """Compare several stocks, ranked best-Sharpe first.

    Tickers that fail to fetch are reported in `skipped` rather than failing
    the whole request — one bad symbol shouldn't sink the batch.
    """
    ranked: list[StockMetrics] = []
    skipped: list[str] = []
    for symbol in request.symbols:
        try:
            ranked.append(compute_metrics(symbol, request.period))
        except RuntimeError:
            skipped.append(symbol.upper())

    if not ranked:
        raise HTTPException(status_code=404,
                            detail="none of the requested tickers could be fetched")

    ranked.sort(key=lambda m: m.sharpe_ratio, reverse=True)
    return CompareResponse(period=request.period, ranked=ranked, skipped=skipped)
