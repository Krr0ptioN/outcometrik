# CALC-03 — Publication, stale detection, and version protocol

**Blocked by:** CALC-02.

## Epic and PRD traceability

- **Epic:** [EPIC-05](epics/EPIC-05-attainment-publication.md)
- **PRD:** PRD §§4, 11.4 FR-406
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an authorized coordinator, I can publish a validated calculation snapshot, so students see a stable result while later corrections remain auditable.

## Rules

- Publication is a separate authorization from grade release and calculation completion.
- At publication time, reauthorize the actor, lock the same input guards and publication series, rebuild the current manifest hash, and verify expected series version.
- Require approved syllabus/mappings, eligible/released inputs, complete required measurements, matching policy/engine versions, and the expected input hash.
- Any mismatch returns 409 and inserts no publication; the previous publication remains readable.
- A publication is immutable and records run, scope, PO-set version, audience, publisher, timestamp, and audit event.
- Historical publications are never overwritten; stale is derived by comparing current inputs with the frozen hash.
- Student endpoints expose only released/published audience snapshots; faculty drafts remain private.
- Publication retry uses an idempotency key and never duplicates a series version.

## Acceptance criteria

- [x] A complete run can be published only by an authorized role (`outcomes.publish` on program scope via `@require_permission("outcomes.publish", scope_field="run.program")`, granted to `administrator` and `program-coordinator` in `access` migration `0008_outcomes_publish_capability`).
- [x] Grade/mapping/roster/eligibility changes produce a visible stale state (`stale: bool` dynamically derived by comparing `publication.input_hash` and `po_set_version` against current manifest hash without mutating the publication).
- [x] Concurrent publication attempts resolve with one immutable series version and safe conflicts (`select_for_update()` on `Program`, `CourseOffering`(s), and series `Publication` rows + partial unique constraints for program and offering series + idempotent retry returning `200 OK` and conflicts returning `409 Conflict`).
- [x] Existing publication remains available after a failed recalculation or rejected stale publication attempt.
- [x] Student reads cannot expose draft or unreleased evidence (`PublicationService.visible_queryset` and `GET /api/v1/publications/{id}/scores/` expose only `audience="student"` publications and strictly filter scores to `student=request.user`).

## Implementation tasks

- [x] Confirm API/data contract and authorization scope against the owning domain module (`outcomes.publish` capability + `Publication` immutable model).
- [x] Implement the smallest vertical slice that satisfies the acceptance criteria (`Publication`, `PublicationService`, `PublicationConflict`, `PublicationController`, `PublicationSerializer`, `PublicationCreateSerializer`, `scoping.scope_publications`).
- [x] Add focused unit/integration coverage for success, invalid input, and denied scope (`apps/api/academic/test_calc03_publications.py`).
- [x] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface (backend-only protocol slice; UI consumption handled by downstream dashboard/reporting stories).
- [x] Update API/UI documentation and verify downstream stories remain compatible.

