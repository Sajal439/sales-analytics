# TODO / Backlog

Prioritized top to bottom. Check items off as they're completed. This file
is the agent's work queue — keep it current.

## P0 — correctness & hygiene

- [x] Add `.gitignore` entries verification — confirm `venv/`, `*.db`,
      `__pycache__/`, `.env` are all ignored (a `.gitignore` is included;
      double check nothing sensitive has been committed already)
- [x] Replace deprecated `datetime.utcnow()` calls (seed.py, models.py) with
      timezone-aware `datetime.now(timezone.utc)`
- [x] Add Alembic migrations instead of relying on
      `Base.metadata.create_all()` — needed before this touches real data
- [x] Pin `bcrypt==4.0.1` is already done (passlib 1.7.4 breaks on bcrypt
      4.1+) — leave as is unless upgrading passlib too

## P1 — tests

- [x] `tests/test_auth.py` — register, login, duplicate username rejection,
      bad password rejection, protected-endpoint access (6 tests passing;
      see `tests/conftest.py` for the isolated-SQLite-DB pattern to reuse)
- [x] `tests/test_analytics.py` — seed a small known dataset in a test DB,
      assert revenue-trend/top-products/kpi-summary numbers are exactly right
      (not just "200 OK")
- [x] `tests/test_forecast.py` — assert Holt-Winters returns the right
      horizon length and non-negative values; assert the Prophet-failure
      path falls back correctly (mock Prophet to raise)
- [x] Wire tests into a `pytest.ini`/`pyproject.toml` with a dedicated test
      DB (don't let tests write to `sales_analytics.db`)

## P2 — real data integration

- [x] Design an ETL path from `invoicing-system` (Node/Express + MongoDB) to
      this service's `Sale`/`Product` tables — likely a scheduled export
      script rather than live coupling, since the stacks are different
- [x] Decide: read-replica sync, nightly batch export, or a shared
      Postgres this API also reads from — document the choice in
      AGENTS.md once made
- [x] Add a `--source=real|synthetic` flag to `app/data/seed.py` or a
      separate `app/data/import_real.py`

## P3 — forecasting quality

- [x] Add a backtesting endpoint/script: hold out the last N days, forecast,
      compare against actuals, report MAPE for both methods
- [x] Per-product / per-category forecasts (currently aggregate-only)
- [x] Simple anomaly flagging on `/analytics/revenue-trend` (flag days >2
      std dev from rolling mean)

## P4 — deployment / polish

- [x] GitHub Actions workflow: run `pytest` + lint on push
- [x] Add `ruff` or `flake8` config and clean up lint warnings
- [x] Rate limiting on `/auth/login` (basic brute-force protection)
- [x] Structured logging (replace default uvicorn logs with something that
      logs request/response for the analytics endpoints)
- [x] Deploy a live demo (Render/Railway/Fly.io) and put the link in
      README.md — a working link matters more than the repo for a resume

## Explicitly out of scope for now

- Frontend/dashboard UI — this is an API-only project by design
- [x] Multi-tenancy — implemented to allow usage by anyone, not just single-business scope
