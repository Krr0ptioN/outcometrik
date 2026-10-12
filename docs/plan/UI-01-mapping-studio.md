# UI-01 — Mapping studio

**Blocked by:** CUR-02, BOOT-02.

## User story

As an instructor or coordinator, I can edit and validate syllabus mapping matrices in the browser, so curriculum configuration is understandable before approval.

## Rules

- Display assessment × LO and LO × PO matrices for one draft syllabus version at a time.
- Allow sparse mappings and weights 0–100 without requiring totals of 100.
- Show invalid range, orphan, incompatible version, unmapped LO/PO, unsaved, conflict, and locked/approved states explicitly.
- Only authorized scoped users can edit; students have no access.
- Save matrix replacements atomically with expected version; a conflict preserves server data and asks the user to refresh.
- Approved versions are read-only; revision creates a new draft.
- Accessibility requires keyboard navigation, labels, focus order, non-color-only status, and an equivalent data table.

## Acceptance criteria

- [ ] The PRD mapping example can be entered through the UI.
- [ ] Validation errors identify the exact matrix cell and rule.
- [ ] Unauthorized and approved-version edits are blocked.
- [ ] Concurrent edit conflict does not discard another user's changes.
- [ ] Keyboard and screen-reader checks cover the matrix workflow.
