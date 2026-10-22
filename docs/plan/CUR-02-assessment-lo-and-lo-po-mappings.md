# CUR-02 — Assessment-to-LO and LO-to-PO mappings

**Blocked by:** CUR-01, OUT-01.

## User story

As an instructor or coordinator, I can configure and validate the two mapping matrices, so each score has a traceable path from assessment to learning outcome to program outcome.

## Rules

- Every mapping belongs to one syllabus version; both endpoints must belong to that syllabus and its bound PO-set.
- A→LO and LO→PO weights are nonnegative relative weights, normally 0–100; their sums are not required to equal 100.
- A zero weight is retained as inactive or ignored; only positive active weights participate.
- Sparse mappings are allowed; every course need not map to all eleven POs unless policy explicitly requires it.
- A LO with no positive A→LO mapping is `UNMAPPED`, never numeric zero.
- A PO with no positive LO→PO mapping is `NOT_ASSESSED`, never numeric zero.
- Matrix replacement is atomic and uses optimistic version checking; conflicts return 409.
- Approval validates orphan endpoints, incompatible versions, invalid ranges, and unreachable configured outcomes.

## Acceptance criteria

- [ ] The PRD's 60/40, 40/100, and 100/50 examples can be entered and validated.
- [ ] Non-100 weight sums are accepted; negative/out-of-range weights are rejected.
- [ ] Cross-syllabus and cross-PO-set mappings cannot be saved.
- [ ] Concurrent edits cannot silently overwrite one another.
- [ ] Validation reports unmapped/orphaned outcomes before approval.
