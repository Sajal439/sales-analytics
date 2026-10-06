"""FastAPI application entry point.

Registers all routers, middleware (structured logging, rate limiting),
and creates tables on startup for SQLite dev mode.
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import analytics, auth, forecast, health, sales
from app.routers.auth import limiter

# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("sales_analytics")

# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sales Analytics & Forecasting API",
    description=(
        "REST API for retail sales analytics and revenue forecasting. "
        "Built with FastAPI, SQLAlchemy 2.0, Pandas, and Prophet/Holt-Winters."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS setup
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiter (slowapi)
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log every request with method, path, status, and duration."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        '{"method":"%s","path":"%s","status":%d,"duration_ms":%.2f}',
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(forecast.router)
app.include_router(sales.router)


# ---------------------------------------------------------------------------
# Startup — create tables for SQLite dev mode
# ---------------------------------------------------------------------------


@app.on_event("startup")
def on_startup():
    """Create all tables if using SQLite (dev mode).

    For PostgreSQL / Supabase deployments, use Alembic migrations instead.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        # Import models so Base.metadata knows about them
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        logger.info("SQLite tables created (dev mode)")
    else:
        logger.info(
            "PostgreSQL detected — skipping auto-create. "
            "Run 'alembic upgrade head' for migrations."
        )
