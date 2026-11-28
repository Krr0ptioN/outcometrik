#!/usr/bin/env bash
# LOAD-01: run a k6 scenario against the gunicorn "api-load" service (benchmark DB only).
# Usage: tools/load-run.sh <smoke|load|stress|spike|soak>
# Needs in .env (or exported): POSTGRES_PASSWORD, DJANGO_SECRET_KEY, PERF_LOAD_PASSWORD
set -euo pipefail
cd "$(dirname "$0")/.."

SCENARIO="${1:-}"
case "$SCENARIO" in
  smoke|load|stress|spike|soak) ;;
  *) echo "Usage: $0 <smoke|load|stress|spike|soak>" >&2; exit 2 ;;
esac

if [ -f .env ]; then set -a; . ./.env; set +a; fi
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"
: "${DJANGO_SECRET_KEY:?Set DJANGO_SECRET_KEY}"
[ -n "${PERF_LOAD_PASSWORD:-}" ] || { echo "Missing load-test credential in .env (see .env.example)" >&2; exit 1; }

export LOAD_POSTGRES_DB="${LOAD_POSTGRES_DB:-outcometrik_perf}"
export LOAD_API_PORT="${LOAD_API_PORT:-8001}"
export PERF_LOAD_PASSWORD

if [ "$LOAD_POSTGRES_DB" = "outcometrik" ]; then
  echo "Refusing to run against the dev database 'outcometrik'." >&2
  exit 1
fi
case "${LOAD_TARGET_HOST:-localhost}" in
  localhost|127.0.0.1) ;;
  *) echo "Refusing to load-test a non-local target." >&2; exit 1 ;;
esac
[ -f docs/perf/seed-meta.json ] || { echo "Run tools/perf-run.sh first (seed-meta.json missing)." >&2; exit 1; }

COMPOSE=(docker compose -f infra/compose.yaml -f infra/compose.load.yaml)
OUT="docs/perf/load/$(date -u +%Y%m%dT%H%M%SZ)-$SCENARIO"
mkdir -p "$OUT"

echo "Starting api-load (gunicorn) on :$LOAD_API_PORT against $LOAD_POSTGRES_DB ..."
IMAGE=outcometrik-api-load:latest
if [ -n "${REBUILD:-}" ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  "${COMPOSE[@]}" build api-load \
    || "${COMPOSE[@]}" build --print api-load \
       | docker buildx bake --allow=network.host --allow=fs.read=.. -f - --load api-load
fi
"${COMPOSE[@]}" up -d --no-build db api-load

SESSION_PATH="${AUTH_SESSION_PATH:-/api/auth/session/}"
for _ in $(seq 1 60); do
  if curl -fs -o /dev/null "http://localhost:$LOAD_API_PORT$SESSION_PATH"; then ready=1; break; fi
  sleep 1
done
[ "${ready:-0}" = 1 ] || { echo "API did not become ready." >&2; exit 1; }

CID="$("${COMPOSE[@]}" ps -q api-load)"
(
  echo "timestamp,container,cpu,mem_usage,mem_pct" > "$OUT/api-docker-stats.csv"
  while true; do
    docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}" "$CID" \
      | sed "s/^/$(date -u +%FT%TZ),/" >> "$OUT/api-docker-stats.csv" || true
    sleep 15
  done
) &
SAMPLER=$!
trap 'kill "$SAMPLER" 2>/dev/null || true; "${COMPOSE[@]}" stop api-load >/dev/null' EXIT

echo "Running k6 scenario '$SCENARIO' -> $OUT"
set +e
docker run --rm --user "$(id -u):$(id -g)" \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/tools/load:/scripts:ro" -v "$PWD/docs/perf:/perf:ro" -v "$PWD/$OUT:/out" \
  -e SCENARIO="$SCENARIO" -e BASE_URL="http://host.docker.internal:$LOAD_API_PORT" \
  -e PERF_LOAD_PASSWORD -e SOAK_MINUTES -e INCLUDE_PDF -e LOAD_STUDENTS \
  -e EXPORT_QUERY -e GRADEBOOK_QUERY -e AUTH_SESSION_PATH -e AUTH_LOGIN_PATH -e API_PREFIX \
  grafana/k6:1.0.0 run --summary-export=/out/summary.json /scripts/k6-load.js
rc=$?
set -e

echo "k6 exit code: $rc (99 = a threshold failed). Results in $OUT"
exit "$rc"
