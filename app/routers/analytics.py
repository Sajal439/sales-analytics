"""Analytics router — KPI summary, revenue trend, top products, category breakdown."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.analytics import (
    CategoryBreakdown,
    KPISummary,
    RevenueTrendPoint,
    TopProduct,
    SlowMovingProduct,
)
from app.services.analytics import (
    get_category_breakdown,
    get_kpi_summary,
    get_revenue_trend,
    get_top_products,
    get_slow_moving_products,
)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(decode_token)],
)


@router.get("/kpi-summary", response_model=KPISummary)
def kpi_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Key performance indicators for the last N days."""
    return get_kpi_summary(db, tenant_id, days=days)


@router.get("/revenue-trend", response_model=list[RevenueTrendPoint])
def revenue_trend(
    granularity: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(90, ge=1, le=730),
    flag_anomalies: bool = Query(False),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Revenue time series with optional anomaly flagging."""
    return get_revenue_trend(
        db, tenant_id, granularity=granularity, days=days, flag_anomalies=flag_anomalies
    )


@router.get("/top-products", response_model=list[TopProduct])
def top_products(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Products ranked by revenue."""
    return get_top_products(db, tenant_id, limit=limit, days=days)


@router.get("/category-breakdown", response_model=list[CategoryBreakdown])
def category_breakdown(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Revenue share by category."""
    return get_category_breakdown(db, tenant_id, days=days)


@router.get("/slow-moving-products", response_model=list[SlowMovingProduct])
def slow_moving_products(
    threshold: int = Query(0, ge=0, description="Max quantity sold to be considered slow-moving"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Products with sales quantity <= threshold (defaults to 0 for dead stock)."""
    return get_slow_moving_products(db, tenant_id, days=days, threshold=threshold)
