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

- [ ] A complete run can be published only by an authorized role.
- [ ] Grade/mapping/roster/eligibility changes produce a visible stale state.
- [ ] Concurrent publication attempts resolve with one immutable series version and safe conflicts.
- [ ] Existing publication remains available after a failed recalculation.
- [ ] Student reads cannot expose draft or unreleased evidence.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

