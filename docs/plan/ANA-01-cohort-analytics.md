# ANA-01 — Cohort analytics

**Blocked by:** CALC-03.

## Epic and PRD traceability

- **Epic:** [EPIC-06](epics/EPIC-06-outcomes-and-reports.md)
- **PRD:** PRD §§6, 11.5 FR-701, FR-703–705
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a coordinator, I can compare published attainment by cohort, course, term, and PO, so weak outcomes are identifiable with honest measurement context.

## Rules

- Analytics read source-of-truth facts or immutable published read models; analytics never mutates attainment.
- Every result identifies program, term, PO-set version, publication status, sample size `n`, coverage, eligibility, and exclusions.
- Compare only compatible PO-set semantics; a changed PO definition is not a performance trend.
- Distinguish draft/provisional from published data and show incomplete/unassessed values as excluded/null, not zero.
- Authorized scope is enforced for program/cohort/course filters and exports.
- Means, medians, distributions, and trends use documented denominators and stable pagination/filter state.
- Published aggregation may be cached/materialized only with a publication/run key and invalidation after a new publication.

## Acceptance criteria

- [x] Coordinator can view PO distributions with n and coverage.
- [x] Incompatible PO versions cannot be silently compared.
- [x] Missing/unassessed/incomplete values do not become zeros.
- [x] Unauthorized program and student-level data are excluded.
- [x] Analytics results can be traced back to a publication and calculation run.

## Implementation tasks

- [x] Confirm API/data contract and authorization scope against the owning domain module.
- [x] Implement the smallest vertical slice that satisfies the acceptance criteria (`CohortAnalyticsService` in `apps/api/academic/services/analytics.py` and `AnalyticsController` in `apps/api/academic/controllers/analytics.py`).
- [x] Add focused unit/integration coverage for success, invalid input, and denied scope (`apps/api/academic/test_ana01_cohort_analytics.py`).
- [x] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface (backend-only analytics API slice; UI integration is tracked in downstream reporting stories).
- [x] Update API/UI documentation and verify downstream stories remain compatible.

## Delivered API contract

- `GET /api/v1/analytics/cohort/` — Guarded by `@require_permission("outcomes.view", scope_field="program")`. Resolves `publication_id` or the latest publication for `program_id` with optional `course_id` / `term_id` filters. Returns read-only per-PO `Decimal` statistics (`mean`, `median`, `min`, `max`, distribution buckets `<50`, `50-69.9`, `70-84.9`, `85-100`, `n`, `population_size`, `coverage`, and `exclusions` for `NOT_ASSESSED`, `INCOMPLETE`, `ALL_EXEMPT`, `UNMAPPED`) with full traceability (`publication_id`, `run_id`, `series_version`, `program_id`, `term_id`, `po_set_version`, `policy_version`, `publication_status`). Never leaks student PII or mutates attainment.
- `GET /api/v1/analytics/trends/` — Guarded by `@require_permission("outcomes.view", scope_field="program")`. Compares compatible publications across terms/cohorts in chronological order; rejects differing `po_set_version` or differing programs with HTTP `400` (`ValidationError(code="incompatible_po_set_version")`).

