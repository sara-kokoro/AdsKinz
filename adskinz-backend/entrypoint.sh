#!/bin/sh
# Applies any pending Alembic migration before the API starts, so a missing
# migration can never again cause "column does not exist" errors in
# production — every deploy self-heals the schema first.
set -e

echo "entrypoint: running 'alembic upgrade head'..."
alembic upgrade head
echo "entrypoint: migrations up to date, starting the API."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
