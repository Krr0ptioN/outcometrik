# AUTH-02 — Scope-bound direct capability grants

**Blocked by:** AUTH-01.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-01.
- **PRD:** PRD §3; §11.1 AUTH-01.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Administrator, I want to grant an individual capability to a user within a named program or offering scope, so that I can delegate one action without changing the user role or widening unrelated access.

## Acceptance criteria

- **Scenario:** Given a user has no role granting Edit Grades and an administrator grants Edit Grades for offering A, When the user edits offering A and then attempts offering B, Then the first action is allowed and the second is denied. Revocation removes the grant unless another applicable grant remains.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [ ] Grant/revoke persistence; scope-aware policy evaluation; audit actor/action/scope; authorization tests for overlap and revocation.
- [ ] Add focused automated tests for success, failure, and scope denial.
- [ ] Document contract and update dependent stories.
