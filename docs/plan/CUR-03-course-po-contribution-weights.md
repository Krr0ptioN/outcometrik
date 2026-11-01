# CUR-03 — Course-to-PO contribution weights

**Blocked by:** CUR-02.

## Epic and PRD traceability

- **Epic:** [EPIC-03](epics/EPIC-03-curriculum.md)
- **PRD:** PRD §§4–5; §11.2 FR-204
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a coordinator, I can assign a course's relevance for each mapped PO, so cumulative student attainment combines courses according to approved 1–5 contribution weights.

## Rules

- Course relevance is a separate weight type from A→LO and LO→PO weights.
- Each contribution is an integer from 1 through 5 and is associated with the approved syllabus/version and PO.
- Contributions are scoped to the program/offering policy and cannot point to an unrelated PO-set.
- Only eligible, approved course POs with complete required inputs participate in published cumulative results.
- No eligible contribution produces null/`NOT_ASSESSED`, not zero.
- Changing a contribution after approval creates a new syllabus/policy revision and makes prior results stale.
- The policy must record who governs weights and whether defaults are catalog-level or offering-level.

## Acceptance criteria

- [ ] Authorized coordinators can set and review integer weights 1–5.
- [ ] Decimal, zero, negative, and greater-than-five values are rejected.
- [ ] The cumulative example `(85×5 + 90×3)/8 = 86.9` is reproducible.
- [ ] Contribution changes invalidate current calculations without mutating publications.
- [ ] Unmapped POs are not assigned misleading contribution scores.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

