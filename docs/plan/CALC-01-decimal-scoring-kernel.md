# CALC-01 — Deterministic Decimal scoring kernel

**Blocked by:** None — can start immediately.

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
