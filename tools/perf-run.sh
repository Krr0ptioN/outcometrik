#!/usr/bin/env bash
# PERF-01: seed + measure on a dedicated, empty database.
# Usage: POSTGRES_DB=outcometrik_perf tools/perf-run.sh --machine-note "<your machine>"
# The database must already exist (see docs/perf/CSE321-report.md or the README note).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${POSTGRES_DB:?Set POSTGRES_DB to a dedicated benchmark database (e.g. outcometrik_perf)}"
PERF_DB="$POSTGRES_DB"

# Load credentials from .env, then force the benchmark database name back.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export POSTGRES_DB="$PERF_DB"

if [ "$POSTGRES_DB" = "outcometrik" ]; then
  echo "Refusing to run against the dev database 'outcometrik'." >&2
  exit 1
fi

cd apps/api
echo "Benchmark database: $POSTGRES_DB"
SEED_ARGS=(--students "${PERF_STUDENTS:-150}" --scale "${PERF_SCALE:-1}")

uv run python manage.py migrate --noinput
uv run python manage.py seed_perf_cse321 "${SEED_ARGS[@]}" --publish
uv run python manage.py perf_measure "$@"
