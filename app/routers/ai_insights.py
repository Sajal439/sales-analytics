"""AI router — Gemini-powered sales insights."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.ai_insights import AIInsightsResponse
from app.services.ai_insights import get_ai_insights

router = APIRouter(
    prefix="/ai",
    tags=["AI Insights"],
    dependencies=[Depends(decode_token)],
)


@router.get(
    "/insights",
    response_model=AIInsightsResponse,
    summary="Gemini-powered sales analyst report",
    description=(
        "Fetches KPIs, top products, category breakdown, and anomaly data for "
        "the requested period, then asks Google Gemini to write a plain-English "
        "executive summary with actionable recommendations.\n\n"
        "Requires `GOOGLE_API_KEY` to be set in the environment. When the key is "
        "absent or the Gemini call fails the endpoint still returns 200 with "
        "`generated: false` and the raw `context_snapshot` so callers can "
        "degrade gracefully."
    ),
)
def ai_insights(
    days: int = Query(30, ge=7, le=365, description="Lookback window in days"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
) -> AIInsightsResponse:
    result = get_ai_insights(
        db,
        tenant_id,
        days=days,
        api_key=settings.GOOGLE_API_KEY,
    )
    return AIInsightsResponse(**result)
