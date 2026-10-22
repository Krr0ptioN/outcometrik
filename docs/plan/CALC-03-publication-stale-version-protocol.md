# CALC-03 — Publication, stale detection, and version protocol

**Blocked by:** CALC-02.

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
