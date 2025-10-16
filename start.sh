#!/usr/bin/env bash
set -e

# Alembic migration (safe to run repeatedly)
if [ -f "/app/alembic.ini" ]; then
  alembic upgrade head || true
fi

# Start FastAPI (listen on $PORT from the platform)
python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"