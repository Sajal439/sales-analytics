# Sales Analytics & Forecasting API

[![CI](https://github.com/<YOUR_GH_USERNAME>/sales-analytics-api/actions/workflows/ci.yml/badge.svg)](https://github.com/<YOUR_GH_USERNAME>/sales-analytics-api/actions/workflows/ci.yml)

A production-ready REST API for retail sales analytics and revenue forecasting,
built with **FastAPI · SQLAlchemy 2.0 · PostgreSQL (Supabase) · Pandas · Prophet + Holt-Winters**.

Designed as a resume/portfolio project for **Goel Traders** — a hardware & building-materials
retailer — but structured for production from the ground up.

---

## Features

| Area | What's included |
|---|---|
| **Auth** | JWT Bearer tokens, bcrypt passwords, rate-limited login (10 req/min per IP via Redis) |
| **Analytics** | Revenue trend (daily/weekly/monthly) with anomaly detection, top products, category breakdown, KPI summary |
| **Forecasting** | Prophet (headline model) with automatic Holt-Winters fallback when cmdstan isn't available |
| **Migrations** | Alembic-managed schema — the sole migration authority for PostgreSQL/Supabase deploys |
| **Observability** | Structured JSON request logging (method, path, status, duration_ms) |
| **CI** | GitHub Actions: ruff lint + pytest on Python 3.11 & 3.12 on every push/PR |

---

## Quick start (local dev — SQLite)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # tweak if needed; defaults to SQLite
python -m app.data.seed          # generates ~18 months of synthetic sales data
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs
Demo login: `demo` / `demo1234`

---

## Supabase deployment

### 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Note your project reference ID and database password

### 2. Configure environment variables

In your deployment platform (Render / Railway / Fly.io), set:

```
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?pgbouncer=true
SECRET_KEY=<openssl rand -hex 32>
REDIS_URL=redis://:[PASSWORD]@[UPSTASH_HOST]:[PORT]   # see Redis section below
```

> **Important**: Use the **Transaction Pooler** URL (port 6543) for the app runtime.
> Use the **Direct** connection (port 5432) only for running migrations.

### 3. Run migrations

```bash
# Use the DIRECT connection string (not the pooler) for DDL:
DATABASE_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres" \
  alembic upgrade head
```

### 4. Seed data (optional)

```bash
DATABASE_URL="<direct-url>" python -m app.data.seed
```

### 5. Redis (for rate limiting)

The login endpoint is rate-limited to **10 requests/minute per IP**.
In production this requires a Redis instance. [Upstash](https://upstash.com) offers
a free tier that works well with Supabase:

1. Create an Upstash Redis database
2. Copy the `redis://` connection string
3. Set it as `REDIS_URL` in your deployment environment

For local dev without Redis, leave `REDIS_URL=memory://` (in-memory, resets on restart).

---

## Run tests

```bash
pytest
```

Tests use an isolated in-memory SQLite database (see `tests/conftest.py`) —
no Supabase or Redis credentials needed.

---

## Docker (Postgres locally)

```bash
docker compose up --build
```

This starts the API with a local Postgres instance. Run migrations before use:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.data.seed
```

---

## API overview

All data endpoints require a `Bearer` token obtained from `POST /auth/login`.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account, returns JWT |
| POST | `/auth/login` | Authenticate, returns JWT (10/min rate limit) |
| GET | `/analytics/kpi-summary` | Total revenue, orders, growth %, top product/region |
| GET | `/analytics/revenue-trend` | Daily/weekly/monthly revenue with optional anomaly flags |
| GET | `/analytics/top-products` | Products ranked by revenue |
| GET | `/analytics/category-breakdown` | Revenue share by category |
| GET | `/forecast/revenue` | 14-day (up to 90-day) Prophet or Holt-Winters forecast |
| GET | `/sales` | Paginated raw sales (filter by product, region) |
| GET | `/products` | Product catalogue |
| GET | `/health` | Health check |

### Anomaly detection

```
GET /analytics/revenue-trend?flag_anomalies=true
```

Adds an `"anomaly": true` flag to any day whose revenue exceeds
the rolling 7-day mean by more than 2 standard deviations.

---

## Architecture

```
app/
├── core/         config, DB session, JWT/password utilities
├── models/       SQLAlchemy ORM models (User, Category, Product, Sale)
├── schemas/      Pydantic request/response schemas
├── services/     Business logic — analytics.py, forecasting.py
└── routers/      Thin HTTP layer — auth, analytics, forecast, sales
alembic/          Database migrations (sole schema authority for PostgreSQL)
tests/            pytest suite — auth, analytics (exact numbers), forecast (mocked Prophet)
```

---

## Forecasting

`GET /forecast/revenue` tries **Prophet** first (trend + weekly/yearly seasonality,
95% uncertainty intervals). If Prophet's cmdstan backend isn't available (common in
sandboxed environments), it silently falls back to **Holt-Winters** exponential
smoothing. The response `method` field tells you which model was used:
`"prophet"`, `"holt_winters"`, or `"holt_winters_fallback"`.

---

## Linting

```bash
ruff check .
ruff format .
```

Config in `pyproject.toml`.
