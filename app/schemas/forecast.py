"""Forecast response schemas."""

from datetime import date

from pydantic import BaseModel


class ForecastPoint(BaseModel):
    """Single forecasted data point."""

    date: date
    predicted_revenue: float
    lower_bound: float | None = None
    upper_bound: float | None = None


class ForecastResponse(BaseModel):
    """Full forecast response with method metadata."""

    method: str  # "prophet", "holt_winters", or "holt_winters_fallback"
    horizon_days: int
    forecast: list[ForecastPoint]


class BacktestResponse(BaseModel):
    """Backtest results with MAPE scores."""

    holdout_days: int
    prophet_mape: float | None
    holt_winters_mape: float | None
    actual_revenue_sum: float
    test_period_start: date
    test_period_end: date
