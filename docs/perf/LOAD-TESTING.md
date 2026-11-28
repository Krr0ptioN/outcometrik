# Load testing (PERF-01, HTTP level)

`perf-run.sh` measures queries and services in-process. These scripts send real HTTP
traffic to the running API using [k6](https://k6.io) (run via Docker, nothing to install).

| Scenario | Shape                                   | Purpose                              |
|----------|-----------------------------------------|--------------------------------------|
| smoke    | 1 user, 1 pass over every endpoint      | Verify the script and URLs           |
| load     | 20 users, 5 min steady                  | Baseline under expected traffic      |
| stress   | 20 → 300 users in steps                 | Find the breaking point              |
| spike    | 5 → 100 users in 10 s, hold, drop to 5  | Recovery after a sudden surge        |
| soak     | 4 users for 30 min + ramp (`SOAK_MINUTES`; 20 VUs saturates the API) | Memory growth (docker stats CSV) |

## Reproduce
```bash
tools/perf-run.sh ...        # benchmark DB seeded (POSTGRES_DB=outcometrik_perf)
export PERF_LOAD_PASSWORD='<choose-a-password>'   # keep out of git
set -a; . ./.env; set +a
(cd apps/api && POSTGRES_DB=outcometrik_perf uv run python manage.py perf_load_users --students 5)
tools/load-run.sh smoke      # always first
tools/load-run.sh load       # then stress | spike | soak
```
Output: `docs/perf/load/<timestamp>-<scenario>/summary.json` and `api-docker-stats.csv`.

## Setup and safety
- API runs under gunicorn (`infra/compose.load.yaml`, service `api-load`), DEBUG off.
  Workers/CPU/memory: `GUNICORN_WORKERS` (4), `LOAD_API_CPUS` (2), `LOAD_API_MEM` (1g). Record them.
- The runner refuses the dev DB `outcometrik` and any non-local target.
- Read-only endpoints only: publication list (staff/student), cohort analytics, gradebook page,
  CSV export (PDF with `INCLUDE_PDF=1`). Data stays valid.
- Thresholds come from `targets.json`; where `p95_ms` is null, **proposed** budgets in
  `k6-load.js` are used. They are proposals, not PRD targets.

## Limitations
- k6, API and PostgreSQL share one machine, so CPU contention lowers the numbers.
- k6 cannot see server memory; the soak run samples `docker stats` every 15 s.
- Login is limited to 10/min per IP, so sessions are created once in `setup()`.
- Write endpoints (grade save, import, publish) are not load-tested.
