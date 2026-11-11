# CUR-02 — Assessment-to-LO and LO-to-PO mappings

**Blocked by:** CUR-01, OUT-01.

## Epic and PRD traceability

- **Epic:** [EPIC-03](epics/EPIC-03-curriculum.md)
- **PRD:** PRD §§4–5; §11.2 FR-203, FR-205
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an instructor or coordinator, I can configure and validate the two mapping matrices, so each score has a traceable path from assessment to learning outcome to program outcome.

## Rules

- Every mapping belongs to one syllabus version; both endpoints must belong to that syllabus and its bound PO-set.
- A→LO weights are nonnegative relative values with no required total. Each active LO→PO link has an integer weight from 1 to 5.
- A zero weight is retained as inactive or ignored; only positive active weights participate.
- Sparse mappings are allowed; every course need not map to all eleven POs unless policy explicitly requires it.
- A LO with no positive A→LO mapping is `UNMAPPED`, never numeric zero.
- A PO with no positive LO→PO mapping is `NOT_ASSESSED`, never numeric zero.
- Matrix replacement is atomic and uses optimistic version checking; conflicts return 409.
- Approval validates orphan endpoints, incompatible versions, invalid ranges, and unreachable configured outcomes.

## Acceptance criteria

- [ ] The PRD 60/40 and 40/100 A→LO weights and 2:1 LO→PO ratio can be entered and validated.
- [ ] Non-100 weight sums are accepted; negative/out-of-range weights are rejected.
- [ ] Cross-syllabus and cross-PO-set mappings cannot be saved.
- [ ] Concurrent edits cannot silently overwrite one another.
- [ ] Validation reports unmapped/orphaned outcomes before approval.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

