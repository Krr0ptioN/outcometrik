# OPS-02 — Audit sensitive changes and rehearse recovery

**Blocked by:** BOOT-01, OPS-01, AUTH-01.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-07.
- **PRD:** PRD §11.6.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Administrator, I want to inspect an audit trail and restore the demo from backup, so that I can establish accountable changes and recoverability.

## Acceptance criteria

- **Scenario:** Given a sensitive grade, permission or publication change occurs, When an authorized operator reviews the event and restores a synthetic-data backup, Then actor/time/target/action are traceable and the demo dataset returns to a usable state without exposing secrets.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [ ] Define auditable event set; redact logs; document synthetic backup/restore rehearsal; record evidence and limitations.
- [ ] Add focused automated tests for success, failure, and scope denial.
- [ ] Document contract and update dependent stories.
