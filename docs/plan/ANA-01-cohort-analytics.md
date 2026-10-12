# ANA-01 — Cohort analytics

**Blocked by:** CALC-03.

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
