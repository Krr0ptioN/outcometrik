# CALC-01 — Deterministic Decimal scoring kernel

**Blocked by:** None — can start immediately.

## Epic and PRD traceability

- **Epic:** [EPIC-05](epics/EPIC-05-attainment-publication.md)
- **PRD:** PRD §§4–5; §11.4 FR-401–403
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a maintainer, I can run the scoring formulas over immutable value objects, so the same versioned inputs always produce the same explainable outcome values.

## Rules

- Normalize each grade as `100 × points_earned / points_possible` using Decimal/Numeric values, never binary floats.
- Compute LO, course PO, and cumulative student PO as weighted means over positive eligible weights.
- Do not round intermediate LO or PO values; round only display/export values to one decimal using the selected policy (proposed `ROUND_HALF_UP`).
- Use a documented precision/context, deterministic operation order, and canonical decimal strings in inputs/results.
- A zero grade participates. A zero denominator returns null with `UNMAPPED`/`NOT_ASSESSED` as appropriate.
- Missing required data yields incomplete status; exempt data is excluded with an authorized reason.
- Reject NaN, infinities, invalid weights, negative grades, and grades above maximum points.
- The kernel has no ORM, network, clock, or authorization dependency.

## Acceptance criteria

- [ ] The PRD examples produce LO1 86.0, LO2 82.9, PO1 85.0, and PO2 82.9 at display precision.
- [ ] Zero, missing, exempt, unmapped, incomplete, and all-exempt cases have distinct results.
- [ ] Repeated runs over identical ordered inputs are byte-for-byte deterministic.
- [ ] Boundary and rounding tests document the selected numeric policy.
- [ ] No intermediate value is quantized to display precision.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

