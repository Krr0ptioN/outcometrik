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

- [ ] Coordinator can view PO distributions with n and coverage.
- [ ] Incompatible PO versions cannot be silently compared.
- [ ] Missing/unassessed/incomplete values do not become zeros.
- [ ] Unauthorized program and student-level data are excluded.
- [ ] Analytics results can be traced back to a publication and calculation run.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

