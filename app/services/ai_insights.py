"""AI Insights service — Gemini-powered sales narrative generator.

Fetches live KPIs, top products, category breakdown, and revenue-trend
anomalies, then asks the Gemini API to write a concise plain-English
analyst report with actionable recommendations.

Graceful degradation:
  - No GOOGLE_API_KEY set  → returns a structured fallback with the raw data.
  - Gemini API error       → logs the error and returns the fallback.
  - google-genai not installed → returns the fallback with an install hint.

The service NEVER raises; callers always get a valid AIInsightsResponse dict.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.services.analytics import (
    get_category_breakdown,
    get_kpi_summary,
    get_revenue_trend,
    get_top_products,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_context_payload(
    db: Session,
    tenant_id: int,
    days: int,
) -> dict:
    """Gather analytics data and return a serialisable dict."""
    kpis = get_kpi_summary(db, tenant_id, days=days)
    top_products = get_top_products(db, tenant_id, limit=5, days=days)
    categories = get_category_breakdown(db, tenant_id, days=days)
    trend = get_revenue_trend(
        db, tenant_id, granularity="daily", days=min(days, 30), flag_anomalies=True
    )

    # Summarise anomaly dates for the prompt
    anomaly_dates = [
        str(p["date"]) for p in trend if p.get("anomaly")
    ]

    # Stringify dates so json.dumps works
    for p in trend:
        if isinstance(p.get("date"), date):
            p["date"] = p["date"].isoformat()

    return {
        "period_days": days,
        "kpis": kpis,
        "top_5_products": top_products,
        "category_breakdown": categories,
        "anomaly_dates": anomaly_dates,
        "recent_daily_trend": trend[-14:],  # last 14 days only — keep prompt tight
    }


def _build_prompt(context: dict) -> str:
    kpis = context["kpis"]
    anomalies = context["anomaly_dates"]
    anomaly_text = (
        f"Revenue anomalies (days > 2σ from rolling mean): {', '.join(anomalies)}"
        if anomalies
        else "No revenue anomalies detected in this period."
    )

    return f"""You are a senior retail sales analyst. Analyse the following JSON data
covering the last {context['period_days']} days and produce a concise executive
summary followed by 3–5 actionable recommendations.

Data:
{json.dumps(context, indent=2)}

Anomaly summary: {anomaly_text}

Your response MUST follow this exact structure:

## Executive Summary
<2–3 paragraph narrative covering revenue performance, growth, standout
products/categories, and any anomalies>

## Key Observations
- <bullet point>
- <bullet point>
(3–5 bullets)

## Recommendations
1. <recommendation with brief rationale>
2. <recommendation with brief rationale>
(3–5 numbered items)

Write for a business audience — no jargon, no markdown code blocks, no raw
JSON in the output. Keep it under 400 words total.
"""


def _fallback_response(context: dict, reason: str) -> dict:
    """Return structured fallback when Gemini is unavailable."""
    return {
        "generated": False,
        "reason": reason,
        "narrative": None,
        "context_snapshot": context,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def get_ai_insights(
    db: Session,
    tenant_id: int,
    days: int = 30,
    *,
    api_key: str | None,
) -> dict:
    """Generate a Gemini-powered analyst narrative for the tenant's sales data.

    Parameters
    ----------
    db:         SQLAlchemy session.
    tenant_id:  Tenant ID extracted from the JWT.
    days:       Lookback window for analytics data.
    api_key:    Google Generative AI API key (from settings).

    Returns a dict that matches the AIInsightsResponse schema — always.
    """
    context = _build_context_payload(db, tenant_id, days)

    if not api_key:
        return _fallback_response(
            context,
            "GOOGLE_API_KEY is not configured. Set it in your .env to enable AI insights.",
        )

    # --- Attempt Gemini call ---
    try:
        from google import genai  # type: ignore[import]
    except ImportError:
        return _fallback_response(
            context,
            "google-genai package is not installed. "
            "Run: pip install google-genai",
        )

    try:
        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(context)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        narrative = response.text.strip()

        return {
            "generated": True,
            "reason": None,
            "narrative": narrative,
            "context_snapshot": context,
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini API call failed: %s", exc)
        return _fallback_response(
            context,
            f"Gemini API error: {exc}",
        )
