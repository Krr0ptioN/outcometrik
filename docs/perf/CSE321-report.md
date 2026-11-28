# CSE321 performance report

- Measured: 2026-11-20 · Commit: ff33bf0 · Seed: perf-cse321-v1 (`docs/perf/seed-meta.json`)
- Machine: HP OMEN, Ryzen 9 8940HX 16C/32T, 32 GB DDR5-5600, NVMe SSD, Windows 11 Home, PostgreSQL 16.15 in Docker (WSL2), Performance mode, default PG config (shared_buffers 160 MB, work_mem 4 MB).
- Reproduce: `POSTGRES_DB=outcometrik_perf tools/perf-run.sh --machine-note "<machine>"` on an empty, dedicated database.
- Full measurements, row counts, table/index/TOAST sizes, scoring, import, lock waits and all `EXPLAIN (ANALYZE, BUFFERS)` plans: [CSE321-results.md](CSE321-results.md), [raw JSON](CSE321-results.json). Pre-fix run: `CSE321-results-before.*`.

## Workload and assumptions
- 150 students, 4 terms, 3 offerings per term (CSE321 each term), 12 assessments, 6 LOs, 11 POs; 12 graded offerings plus one import target. 3% exempt grades, 2% withdrawn enrollments, no missing grades.
- Warm cache (3 warmup calls, 30 iterations, cache hit ratio about 1.0). The "first" column is the first call in a fresh process, not a cold OS cache.
- Concurrency 1 and 8 threads in one Python process (pessimistic for Python-side work). Data state per row: draft, published, or published (stale).

## Result: PRD comparison
The PRD defines no latency targets that were available for this run, so no PASS/MISS verdicts are given. `targets.json` is ready to be filled in; the results file will then show verdicts.

## Findings and decisions
| Finding | Evidence | Decision |
|---|---|---|
| Student publication list slow (query level; over HTTP it is still about 1.9 s, see k6 section) | 1,561 ms p50; plan 1,370 ms, 33,431 buffer hits (DISTINCT over a join to all scores, sorting the manifest JSON) | **Fixed**: `EXISTS` subquery in `scope_publications`, `defer("run__manifest")`. Now 18 ms p50, plan 0.39 ms, 36 buffer hits. |
| Staff publication list slow | 375 ms p50, SQL only 60 ms | **Fixed** by the same change: 22 ms p50. |
| `is_stale()` rebuilds the full manifest per read | Program: 789 ms, 126 queries; offering: 62 ms | **Deferred**: follow-up #1 |
| Program cohort summary / trends | 1,480 ms / 603 ms, dominated by `is_stale()` | **Deferred**: follow-up #1 |
| Calculation capture holds row locks during manifest build | 8 workers x3 calls took 2.5 s wall; waiting locks seen in 91 of 96 samples; 0 deadlocks | **Deferred**: follow-up #2 |
| Scoring persistence dominates | about 340 of 460 ms is run and score insert (2,499 rows, 2.1 MB evidence) | Recorded; no change |
| CSV import throughput | about 1,100 rows/s create, about 930 rows/s update (10,000-row max is about 10 s) | **Deferred**: follow-up #3 |
| Storage growth | Program run: 8.5 MB manifest (2.2 MB stored), 16 MB evidence per recalculation | **Deferred**: follow-up #4 |
| No index problems | Remaining seq scans are on tables with fewer than 100 rows | No index change |

## Scaling follow-ups to create
1. Cheaper staleness check using stored input revisions, keeping the hash authoritative (CALC-03 owners decide).
2. Narrow lock scope in calculation capture: build the manifest before locking.
3. Bulk grade writes in CSV import.
4. Retention policy for old calculation manifests and evidence.

## Limitations
- Synthetic, uniform data; single host, client and database on one machine.
- Scoring mutates grades by queryset update (no history rows) on a benchmark-only database.
- The pre-fix run was on a different database (dev DB, same seed and machine) than the post-fix run; the plan change explains the improvement.
- Gradebook reads use a proxy query, and gradebook writes through the service are not measured.
- 8-thread numbers share one Python process and GIL.

## HTTP load testing (k6)

Method, scenarios and reproduction: [LOAD-TESTING.md](LOAD-TESTING.md). Command: `tools/load-run.sh <smoke|load|stress|spike|soak>` (`REBUILD=1` rebuilds the image after API code changes).
Machine: same HP OMEN as above, k6 in Docker (host.docker.internal) · API: gunicorn, 4 sync workers, 2 CPU, 1 GiB · PostgreSQL 16.15 ·
Seed: perf-cse321-v1 (re-seeded 2026-11-20 17:24 UTC, rng_seed 321), 150 students · Dates: load 2026-11-20, stress/spike/soak 2026-11-28 · Data state: published.
Thresholds are the ones defined in `tools/load/k6-load.js` (p95 < 300/500/800/800/2000 ms, error rate < 1%), not PRD targets; the PRD has none.

| Scenario | Peak VUs | Requests | Error rate | Worst endpoint p95 | Thresholds |
|----------|----------|----------|------------|--------------------|------------|
| load     | 20  | 397  | 0.00%  | 26.34 s (publication_list_staff) | 5 of 5 latency thresholds MISSED; error rate passed |
| stress   | 300 | 1,356 | 74.33% | 59.99 s (k6 timeout)             | all MISSED; breaking point between 20 VUs (0% errors, ~16 s avg latency) and 300 VUs, not narrowed further |
| spike    | 100 | 182  | 50.00% | 59.99 s                          | all MISSED; not recovered within the run (timeouts still firing after ramp-down) |
| soak (4 VUs, 33 min) | 4 | 1,573 | 0.12% (2 requests) | 6.86 s (publication_list_staff) | 4 of 5 latency thresholds MISSED (gradebook 97 ms passed); API memory start -> last in-run sample: 246 -> 955 MiB, peak 1,010 MiB |

Per-endpoint p95 in the 20 VU load run: publication_list_staff 26.34 s (target 500 ms), publication_list_student 22.36 s (300 ms), analytics_cohort_program 22.01 s (800 ms), export_cohort_csv 22.4 s (2000 ms), gradebook_page_200 19.13 s (800 ms). All MISSED.
Single user (smoke): publication_list_staff 3,814 ms (first request, includes cold start), publication_list_student 1,963 ms, analytics 1,909 ms, export CSV 1,889 ms, gradebook 50 ms.

### Findings
- The API container is CPU-bound: average 193% CPU against a 2 CPU limit during the 20 VU load run, about 1 request/s.
- Publication list, analytics and export share one cost: `is_stale()` rebuilds the input manifest on every read (callers: `serializers.py` `get_stale` per row, `services/analytics.py`, `reports/readers.py`). Gradebook does not call it (50 ms alone). It only fails under stress because it queues in the same 4 workers.
- `get_program_outcomes` in `PublicationSerializer` runs one query per publication row (N+1).
- Soak memory: rose from 246 to about 830 MiB in the first 4 minutes (warm-up), then varied between about 730 and 1,010 MiB with a slight upward drift, peak about 99% of the 1 GiB limit. Inconclusive as a leak. No OOM kill and no worker restarts (OOMKilled=false, Restarts=0).

### Decision
Deferred: follow-up #1 above (cheaper staleness check). Added follow-ups:
5. Compute `stale` only on the detail endpoint, or cache the current input hash per publication, and prefetch `program_outcomes` per (program, po_set_version).
6. Re-run the soak with a higher memory limit or per-worker memory sampling, to separate a leak from allocator behaviour.
7. Re-run load/stress after follow-up #1 or #5 to get a real breaking point; at about 1.9 s CPU per request the current one is about 20 VUs.

### Limitations of the HTTP runs
- Soak ran at 4 VUs, not 20, because 20 VUs saturates the API and would measure queueing, not steady operation. The 20 VU load run is the saturation evidence.
- Stress breaking point is only bracketed. Spike recovery was not observed. Per-request timeouts are k6's default 60 s, so p95 = 59.99 s means "timed out".
- 2 failed soak requests (1 analytics, 1 export): cause not investigated.
- Load generator, API and database share one laptop; no cold-cache control; load and later runs are on different days against the same database.
- Memory was sampled by `docker stats` about every 15 s; the last sample (8 MiB) is the container shutting down and is excluded.
