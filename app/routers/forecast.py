"""Forecast router — revenue forecasting endpoint."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.forecast import ForecastResponse, BacktestResponse
from app.services.forecasting import get_forecast, run_backtest

router = APIRouter(
    prefix="/forecast",
    tags=["Forecast"],
    dependencies=[Depends(decode_token)],
)


@router.get("/revenue", response_model=ForecastResponse)
def forecast_revenue(
    horizon_days: int = Query(14, ge=1, le=90),
    product_id: int | None = Query(None),
    category_id: int | None = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Forecast future revenue using Prophet (or Holt-Winters fallback)."""
    if product_id and category_id:
        raise HTTPException(status_code=400, detail="Provide either product_id or category_id, not both")
    return get_forecast(
        db, tenant_id, horizon_days=horizon_days, product_id=product_id, category_id=category_id
    )


@router.get("/backtest", response_model=BacktestResponse)
def backtest_forecasts(
    holdout_days: int = Query(30, ge=7, le=90),
    product_id: int | None = Query(None),
    category_id: int | None = Query(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Backtest Prophet vs Holt-Winters by holding out the last N days."""
    if product_id and category_id:
        raise HTTPException(status_code=400, detail="Provide either product_id or category_id, not both")
    res = run_backtest(
        db, tenant_id, holdout_days=holdout_days, product_id=product_id, category_id=category_id
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
