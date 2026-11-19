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

- [x] Offering and cumulative calculations produce expected canonical values and statuses.
- [x] Outcome scores link to frozen grade/mapping/evidence records.
- [x] Missing required grades block publication eligibility but remain visible in preview.
- [x] A correction or newly eligible course causes a new input hash and run.
- [x] Retried identical calculation requests return the same completed run identity.

## Implementation tasks

- [x] Confirm API/data contract and authorization scope against the owning domain module.
- [x] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [x] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [x] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface (backend-only calculation engine and REST endpoints; UI surface is in downstream EPIC-05 stories).
- [x] Update API/UI documentation and verify downstream stories remain compatible.

## Implemented API & Data Contract

- **Models (`apps/api/academic/models.py`, migration `0009_calculation_runs_and_scores`)**:
  - `CalculationRun` (`scope_kind`: `offering` | `program`, `status`: `pending` | `completed` | `failed`, `po_set_version`, `engine_version`, `policy_version="calc-policy-v1"`, `input_hash`, `manifest`, `is_complete_for_publication`, `error_detail`, `created_by`, `completed_at`, with partial unique idempotency constraints for completed runs).
  - `OutcomeScore` (`level`: `lo` | `course_po` | `cumulative_po`, `status`: `OK` | `INCOMPLETE` | `UNMAPPED` | `NOT_ASSESSED` | `ALL_EXEMPT`, Decimal `value`/`numerator`/`denominator`/`coverage`, and structured `evidence` JSON linking frozen grades, mappings, and contributions).
- **Service (`apps/api/academic/services/calculations.py`)**:
  - `@injectable class CalculationService` with two-phase capture (deterministic `Program` + `CourseOffering` row locks) -> pure Decimal compute (`calc.kernel`) outside locks -> short atomic persist.
  - Exposes `build_manifest_and_hash(...)` for downstream `CALC-03` publication and stale detection.
- **HTTP Endpoints (`apps/api/academic/controllers/calculations.py`)**:
  - `GET /api/v1/calculation-runs/` and `GET /api/v1/calculation-runs/{id}/` (staff-scoped; never exposed to students).
  - `POST /api/v1/calculation-runs/offering/` (`@require_permission("grades.view", scope_field="offering")`).
  - `POST /api/v1/calculation-runs/program/` (`@require_permission("outcomes.view", scope_field="program")`).
  - `GET /api/v1/calculation-runs/{id}/scores/` (returns computed `OutcomeScore` rows with `display_value` and `evidence`).

