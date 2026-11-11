# PERF-01 — Query-plan and storage measurements

**Blocked by:** ANA-01.

## Epic and PRD traceability

- **Epic:** [EPIC-07](epics/EPIC-07-quality-demo-delivery.md)
- **PRD:** PRD §§8, 11.6; CSE321 evidence only
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As the project team, I can measure query plans, latency, row counts, and storage for a realistic CSE321 dataset, so performance claims are evidence-based.

## Rules

- Use PostgreSQL with a documented machine, configuration, dataset size, seed version, and measurement date.
- Measure exact row counts and both raw table size and total size including indexes/TOAST; do not substitute planner estimates for counts.
- Capture `EXPLAIN (ANALYZE, BUFFERS)` for scoped CRUD, gradebook, evidence drill-down, publication read, analytics, and export queries.
- Measure p50/p95 latency, query count, lock waits, connection usage, scoring duration, evidence rows/bytes, and import throughput.
- Include cold/warm cache assumptions, concurrency, filters, pagination, and whether data is draft or published.
- Do not optimize from synthetic numbers without recording the workload and reproduction command.
- Compare measurements with proposed PRD targets; report misses honestly and create a scaling follow-up when necessary.

## Acceptance criteria

- [ ] A reproducible benchmark dataset and command are documented.
- [ ] Required query plans, storage sizes, counts, and latency percentiles are recorded.
- [ ] The scoring benchmark includes evidence persistence, not only arithmetic.
- [ ] Any slow query has an explained index/query/model decision or a documented deferral.
- [ ] The CSE321 report contains measured results with assumptions and limitations.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

