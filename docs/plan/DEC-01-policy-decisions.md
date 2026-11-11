# DEC-01 — Resolve scoring and publication policy decisions

**Blocked by:** CALC-01, CUR-03, CALC-03.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-05.
- **PRD:** PRD §12.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Program coordinator, I want to confirm proposed attempt, weight ownership, release and rounding policies, so that I can ensure calculations and publication follow approved institutional rules.

## Acceptance criteria

- **Scenario:** Given policy choices remain proposals, When the coordinator approves or defers each question, Then the decision and effective version are recorded and linked to tests before affected production workflows depend on it.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [ ] Record decision owner/date/effective version; define test updates; keep unresolved options explicit; do not invent policy.
- [ ] Add focused automated tests for success, failure, and scope denial.
- [ ] Document contract and update dependent stories.
