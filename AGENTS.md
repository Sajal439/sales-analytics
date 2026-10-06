# AGENTS.md

Context for any AI coding agent (Claude Code, Cursor, etc.) working on this
repo. Read this before making changes.

## What this is

A FastAPI service that turns raw retail sales transactions into revenue
analytics and forecasts. Originally scaffolded as a resume/portfolio project;
the goal now is to harden it toward something closer to production quality
and, eventually, point it at real sales data from a sister project
(`invoicing-system`, a Node/Express + MongoDB invoicing app — different repo,
different stack, not wired in yet).

## Stack

FastAPI · SQLAlchemy 2.0 · PostgreSQL (SQLite for local dev) · Pandas ·
Prophet + statsmodels (forecasting) · JWT via python-jose · Docker.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.data.seed      # generates ~18mo of synthetic sales data
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs. Demo login: `demo` / `demo1234`.

Docker: `docker compose up --build` (Postgres instead of SQLite).

## Run tests

```bash
pytest
```

Test coverage is currently thin (see TODO.md) — expanding it is one of the
priority tasks.

## Architecture / conventions

- `app/core/` — config, DB session, JWT/password handling. Don't put business
  logic here.
- `app/models/` — SQLAlchemy ORM models only.
- `app/schemas/` — Pydantic request/response models. Every router response
  should have a `response_model`.
- `app/services/` — actual business logic (analytics aggregation, forecasting
  math). Routers should stay thin and just call into services.
- `app/routers/` — one router per resource, registered in `app/main.py`.
  All data endpoints depend on `decode_token` (JWT-protected).
- Forecasting: `get_forecast()` in `app/services/forecasting.py` is the single
  entry point. It tries Prophet first and falls back to Holt-Winters
  (`forecast_holt_winters`) on any failure — **preserve this fallback
  behavior**, don't let a Prophet failure become a 500.
- New endpoints: add a Pydantic schema, a service function, a router function
  that's thin (auth dep + call service + return), then register the router
  in `main.py` if it's a new router.

## Known environment quirk

Prophet requires a compiled `cmdstan` backend downloaded on first install.
This fails in network-sandboxed environments (blocked GitHub release
fetch) — that's expected there, not a bug. It installs fine with normal
internet access (`pip install prophet` pulls cmdstanpy, which needs
`python -m cmdstanpy.install_cmdstan` or builds it on Docker). If Prophet
can't load, the API should silently serve Holt-Winters instead — verify
this fallback still works after any changes to `forecasting.py`.

## Data

`app/data/seed.py` generates synthetic sales data (trend growth, weekend
spikes, a festive-season bump, a monsoon dip) so the API works without real
data. 

**ETL Architecture**: We use a nightly batch export from the `invoicing-system` 
(Node/Express + MongoDB) to export real transaction data to JSON. This service 
ingests that JSON, decoupling the two stacks. See TODO.md for wiring in real 
transaction data instead, or use `python -m app.data.seed --source=real --file=<path.json>` 
once implemented.

## Priority tasks

See TODO.md for the current prioritized backlog. Work top to bottom unless
told otherwise. Before starting a task, check it isn't already partially
done. After finishing a task, run `pytest`, run the app and hit the
affected endpoint manually via `/docs` or curl, then check the box in
TODO.md.

## Things not to do

- Don't remove the Prophet → Holt-Winters fallback.
- Don't commit `.env`, `sales_analytics.db`, or `__pycache__` (already in
  `.gitignore`).
- Don't hardcode `SECRET_KEY` outside `app/core/config.py`'s default (which
  is only a dev fallback — real deployments must set it via env var).
- Don't add new dependencies without a reason noted in the commit message —
  this needs to stay a legible resume project, not accrue randomly.
