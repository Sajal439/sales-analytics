"""AI Insights response schema."""

from typing import Any

from pydantic import BaseModel


class AIInsightsResponse(BaseModel):
    """Response from the /ai/insights endpoint.

    When `generated` is True, `narrative` holds the Gemini-written report.
    When `generated` is False, `reason` explains why (missing key, API error,
    etc.) and `context_snapshot` still contains the raw analytics data so the
    caller can render it without a second round-trip.
    """

    generated: bool
    reason: str | None = None
    narrative: str | None = None
    context_snapshot: dict[str, Any]
