# CALC-02 — Offering and cumulative outcome calculation

**Blocked by:** CALC-01, GRD-01, CUR-03.

## User story

As faculty or a coordinator, I can calculate course and cumulative PO attainment from a frozen input set, so results are reproducible and traceable to source grades and mappings.

## Rules

- Capture a canonical manifest containing policy/engine versions, PO/syllabus versions, mappings, grade revisions, eligibility, releases, roster, course contributions, and exclusions.
- Lock program/offering revision guards in deterministic order during capture; never hold locks while doing arithmetic.
- Store a content hash and immutable manifest before calculation; calculate outside the capture transaction.
- Calculate assessment → LO → course PO → student PO and retain numerator, denominator, coverage, status, and evidence links.
- Proposed cumulative attempt policy is latest completed approved attempt per catalog course; the selected policy must be explicit and versioned.
- Published calculations require complete required inputs; drafts may show incomplete previews with visible status.
- New eligible offerings, enrollments, grade revisions, release changes, or mapping changes invalidate the captured hash.
- A complete run is idempotent by scope + input hash + engine version + policy version; failed runs expose no partial scores.

## Acceptance criteria

- [ ] Offering and cumulative calculations produce expected canonical values and statuses.
- [ ] Outcome scores link to frozen grade/mapping/evidence records.
- [ ] Missing required grades block publication eligibility but remain visible in preview.
- [ ] A correction or newly eligible course causes a new input hash and run.
- [ ] Retried identical calculation requests return the same completed run identity.
