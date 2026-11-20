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

- **Confirmed API contracts (`cache: 'no-store'`):**
  - `GET /api/v1/publications/?program=<program_id>` — lists coordinator-scoped immutable publications (`id`, `program`, `offering`, `term`, `run`, `series_version`, `po_set_version`, `audience`, `published_at`, `stale`).
  - `GET /api/v1/analytics/cohort/?program_id=<uuid>&publication_id=<uuid>&term_id=<uuid>&course_id=<uuid>` — returns traceability metadata (`publication_id`, `run_id`, `series_version`, `program_id`, `term_id`, `po_set_version`, `policy_version`, `publication_status`, `sample_size`, `population_size`, `coverage`, `exclusions`) and per-PO distributions (`<50`, `50-69.9`, `70-84.9`, `85-100`) and exclusions (`NOT_ASSESSED`, `INCOMPLETE`, `ALL_EXEMPT`, `UNMAPPED`).
  - `GET /api/v1/analytics/trends/?program_id=<uuid>&po_set_version=<int>&publication_ids=<uuids>` — returns chronological trend points for compatible `po_set_version` publications and rejects incompatible PO-set comparisons with HTTP `400` (`incompatible_po_set_version`).

## Implementation tasks

- [x] Confirm analytics API; implement filters/loading/empty/error states; accessible chart/table; scope tests.
- [x] Add focused automated tests for success, failure, and scope denial.
- [x] Document contract and update dependent stories.
