# IMP-01 — CSV grade import with dry-run and atomic apply

**Blocked by:** GRD-01.

## Epic and PRD traceability

- **Epic:** [EPIC-04](epics/EPIC-04-grading.md)
- **PRD:** PRD §§7, 11.1, 11.3 FR-303–304
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As authorized faculty, I can validate and apply a grade CSV safely, so one malformed row never silently corrupts an offering gradebook.

## Rules

- Proposed initial limits: UTF-8 CSV, 5 MB, 10,000 rows, explicit required columns, sanitized filenames, and safe formula-prefix escaping on exports.
- Dry-run parses, validates headers/IDs/states/ranges/duplicates/scope, reports row/column errors, and writes no grade facts.
- Apply reauthorizes the actor, revalidates against current syllabus/enrollment/revision, and uses an idempotency key plus file checksum.
- Default apply is all-or-nothing; valid rows are not committed when any required row fails.
- Repeating the same key/body returns the committed import; reusing a key with a different body returns 409.
- Import writes grade entries, history, batch metadata, revision, and audit atomically.
- Unreleased imports remain faculty-only until an explicit release action.
- Temporary files are private and expire under an approved retention policy.

## Acceptance criteria

- [ ] Dry-run returns actionable errors and leaves the gradebook unchanged.
- [ ] Valid CSV applies once and is safe to retry.
- [ ] Malformed, stale, unauthorized, duplicate, and out-of-range rows fail safely.
- [ ] Concurrent apply cannot create duplicate grade history.
- [ ] Import actor, checksum, counts, errors, and resulting revision are auditable.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

