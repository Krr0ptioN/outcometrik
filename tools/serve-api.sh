#!/usr/bin/env sh
set -eu
repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
if [ -f "$repo_root/.env" ]; then
  set -a
  . "$repo_root/.env"
  set +a
fi
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "Set POSTGRES_PASSWORD in the repository .env file before running the API." >&2
  exit 1
fi
cd "$repo_root/apps/api"
exec uv run python manage.py runserver 0.0.0.0:8000
