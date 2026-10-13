#!/bin/sh
set -eu
PORT="${PORT:-8741}"
WORKERS="${WEB_CONCURRENCY:-2}"
exec gunicorn backend.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w "$WORKERS" \
  -b "0.0.0.0:${PORT}" \
  --timeout 120
