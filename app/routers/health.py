"""Health check endpoint — no auth required."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Simple health check."""
    return {"status": "healthy"}
