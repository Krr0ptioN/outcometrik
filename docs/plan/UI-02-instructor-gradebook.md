# UI-02 — Instructor gradebook

**Blocked by:** GRD-01, BOOT-02.

## Epic and PRD traceability

- **Epic:** [EPIC-07](epics/EPIC-07-quality-demo-delivery.md)
- **PRD:** PRD §§6, 11.3 FR-301–306
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an instructor, I can view an offering roster by assessment and enter grades with clear states, so I can complete grading without confusing zero, missing, or exempt values.

## Rules

- Show only assigned offering rosters and permitted assessments.
- Use a grid with student rows and assessment columns, stable pagination/filtering, keyboard navigation, and explicit save state.
- Represent zero, missing, exempt, withdrawn, invalid, unreleased, and released distinctly; missing is not zero.
- Validate points against maximum points before submission and surface row/cell errors without silently overwriting valid cells.
- Send expected gradebook revision and idempotency information for bulk edits; display 409 conflicts with refresh/retry guidance.
- Student identifiers and grades are private and must not leak through URLs, client state, logs, or exports.

## Acceptance criteria

- [ ] Instructor can grade an authorized roster and see persisted values after reload.
- [ ] Zero, missing, and exempt values remain distinguishable.
- [ ] Invalid cells are rejected without partial unintended updates.
- [ ] Unauthorized offerings and student records remain inaccessible.
- [ ] Keyboard operation and accessible error announcements work for the grid.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

