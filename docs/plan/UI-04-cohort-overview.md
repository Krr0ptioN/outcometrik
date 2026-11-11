# UI-04 — Cohort overview

**Blocked by:** ANA-01, AUTH-01.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-06.
- **PRD:** PRD §6; §11.5 FR-701, FR-703–705.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Program coordinator, I want to inspect cohort outcome distributions and coverage, so that I can identify weak or unmeasured outcomes with the correct population context.

## Acceptance criteria

- **Scenario:** Given a published cohort has one measured zero and one unassessed student, When the coordinator views a PO, Then the view shows zero for n=1 and missing coverage separately, with publication and PO-set version.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [ ] Confirm analytics API; implement filters/loading/empty/error states; accessible chart/table; scope tests.
- [ ] Add focused automated tests for success, failure, and scope denial.
- [ ] Document contract and update dependent stories.
