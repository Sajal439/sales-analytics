#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head || echo "Migrations failed or skipped."

echo "Starting server with Gunicorn (4 workers)..."
exec gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
