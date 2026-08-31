#!/bin/sh
set -eu

mkdir -p "$(dirname "$BOTEN_DATABASE_PATH")" "$BOTEN_UPLOAD_DIR"
python -m alembic upgrade head
exec uvicorn backend.main:app --host 0.0.0.0 --port 8001 --proxy-headers --forwarded-allow-ips="*"
