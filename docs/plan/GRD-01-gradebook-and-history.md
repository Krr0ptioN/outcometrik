# GRD-01 — Gradebook and grade history

**Blocked by:** CUR-01, AUTH-01.

## Epic and PRD traceability

- **Epic:** [EPIC-04](epics/EPIC-04-grading.md)
- **PRD:** PRD §§4, 11.3 FR-301–302, FR-305–306
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an authorized instructor, I can record and correct assessment grades for an offering roster, so raw measurement facts are accurate, scoped, and auditable.

## Rules

- A grade belongs to one enrolled student, assessment, offering/syllabus, and grade batch.
- `points_earned` is stored against `points_possible`; it must be within range and use Decimal/Numeric semantics.
- Zero is a real measured value. Missing, exempt, withdrawn, and incomplete are explicit states, not zero.
- One active grade entry exists per enrollment/assessment; every change appends old/new value, state, actor, reason, timestamp, and revision.
- Manual writes require active enrollment, matching approved assessment, object permission, and expected row/version where applicable.
- Corrections after release/publication require authorization and reason; they increment the input revision and mark dependent publications stale.
- Grade mutations and audit history are atomic; failed writes do not partially alter the gradebook.
- Students see only grades from released batches; faculty previews may include unreleased values.

## Acceptance criteria

- [ ] An instructor can enter valid grades and explicitly choose zero/missing/exempt.
- [ ] Invalid ranges, inactive enrollment, and unauthorized offering access fail safely.
- [ ] Corrections preserve a complete history and require a reason when policy requires it.
- [ ] Concurrent updates return a version conflict instead of last-write-wins.
- [ ] Cross-student and unreleased-grade access tests pass.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

