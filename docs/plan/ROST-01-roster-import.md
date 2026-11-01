# ROST-01 — Preview and import student rosters

**Blocked by:** ACAD-01, AUTH-01.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-02.
- **PRD:** PRD §11.1 FR-105; §11.3.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Program coordinator, I want to preview and import an offering roster from CSV, so that I can avoid duplicate or incorrectly scoped enrollments.

## Acceptance criteria

- **Scenario:** Given a coordinator uploads a roster containing valid, duplicate and invalid rows, When they preview and confirm it, Then valid rows are applied atomically, duplicate/invalid rows are identified, and a failed/stale preview writes nothing.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [ ] Define CSV contract and limits; validate program/offering scope; duplicate detection; atomic apply; audit; tests.
- [ ] Add focused automated tests for success, failure, and scope denial.
- [ ] Document contract and update dependent stories.
