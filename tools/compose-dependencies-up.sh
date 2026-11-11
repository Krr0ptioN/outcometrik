#!/usr/bin/env sh
set -eu
repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
if [ -f "$repo_root/.env" ]; then
  set -a
  . "$repo_root/.env"
  set +a
fi
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "Set POSTGRES_PASSWORD in .env or in your shell before starting the local database." >&2
  exit 1
fi
exec docker compose -f infra/compose.dependencies.yaml up -d "$@"
