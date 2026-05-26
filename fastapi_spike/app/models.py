"""Pydantic models for the Returns Assistant API.

FastAPI reads these straight off the endpoint type hints, so each model drives
three things at once: request validation, the response shape, and the
auto-generated OpenAPI docs at /docs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class StockMetrics(BaseModel):
    """Headline return/risk metrics for one stock over a period."""
    symbol: str
    start_date: str
    end_date: str
    trading_days: int
    total_return_pct: float = Field(description="Cumulative return over the period")
    annualised_return_pct: float = Field(description="CAGR")
    annualised_volatility_pct: float = Field(description="Return std, x sqrt(252)")
    sharpe_ratio: float = Field(description="Excess return per unit of volatility")
    max_drawdown_pct: float = Field(description="Largest peak-to-trough drop")


class CompareRequest(BaseModel):
    """Request body for POST /compare — two or more tickers to rank."""
    symbols: list[str] = Field(
        min_length=2,
        examples=[["RELIANCE.NS", "TCS.NS", "INFY.NS"]],
        description="NSE tickers, '.NS' suffix",
    )
    period: str = Field(default="1y", examples=["1y"],
                        description="yfinance period, e.g. 6mo / 1y / 2y")


class CompareResponse(BaseModel):
    """Response for POST /compare — metrics per stock, ranked by Sharpe."""
    period: str
    ranked: list[StockMetrics]
    skipped: list[str] = Field(default_factory=list,
                               description="Tickers that could not be fetched")


class HealthResponse(BaseModel):
    """Liveness response for GET /healthz."""
    status: str
    service: str
