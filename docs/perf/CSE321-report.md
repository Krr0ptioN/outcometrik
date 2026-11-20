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
| Student publication list slow | 1,561 ms p50; plan 1,370 ms, 33,431 buffer hits (DISTINCT over a join to all scores, sorting the manifest JSON) | **Fixed**: `EXISTS` subquery in `scope_publications`, `defer("run__manifest")`. Now 18 ms p50, plan 0.39 ms, 36 buffer hits. |
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