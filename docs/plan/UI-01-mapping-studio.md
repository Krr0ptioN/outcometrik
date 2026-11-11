# UI-01 — Mapping studio

**Blocked by:** CUR-02, BOOT-02.

## Epic and PRD traceability

- **Epic:** [EPIC-07](epics/EPIC-07-quality-demo-delivery.md)
- **PRD:** PRD §§6, 11.2 FR-205–207
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an instructor or coordinator, I can edit and validate syllabus mapping matrices in the browser, so curriculum configuration is understandable before approval.

## Rules

- Display assessment × LO and LO × PO matrices for one draft syllabus version at a time.
- Allow sparse mappings. A→LO weights are nonnegative relative values without a required total; LO→PO links are integers 1–5.
- Show invalid range, orphan, incompatible version, unmapped LO/PO, unsaved, conflict, and locked/approved states explicitly.
- Only authorized scoped users can edit; students have no access.
- Save matrix replacements atomically with expected version; a conflict preserves server data and asks the user to refresh.
- Approved versions are read-only; revision creates a new draft.
- Accessibility requires keyboard navigation, labels, focus order, non-color-only status, and an equivalent data table.

## Acceptance criteria

- [ ] The PRD mapping example can be entered: A→LO 60/40 and 40/100; LO→PO 2:1 and 1.
- [ ] Validation errors identify the exact matrix cell and rule.
- [ ] Unauthorized and approved-version edits are blocked.
- [ ] Concurrent edit conflict does not discard another user's changes.
- [ ] Keyboard and screen-reader checks cover the matrix workflow.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

