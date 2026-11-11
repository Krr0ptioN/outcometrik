# CALC-02 — Offering and cumulative outcome calculation

**Blocked by:** CALC-01, GRD-01, CUR-03.

## Epic and PRD traceability

- **Epic:** [EPIC-05](epics/EPIC-05-attainment-publication.md)
- **PRD:** PRD §§4–5; §11.4 FR-402, FR-404–405
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

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
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

