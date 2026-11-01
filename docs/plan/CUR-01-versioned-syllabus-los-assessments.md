# CUR-01 — Versioned syllabus, learning outcomes, and assessments

**Blocked by:** ACAD-01.

## Epic and PRD traceability

- **Epic:** [EPIC-03](epics/EPIC-03-curriculum.md)
- **PRD:** PRD §6; §11.2 FR-201, FR-202, FR-206–207
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an instructor, I can draft and submit a versioned syllabus for an offering, so its learning outcomes and assessments are approved before official scoring.

## Rules

- A syllabus version belongs to one offering and one PO-set version; only one version is active for official use.
- Learning outcomes and assessments belong to the same syllabus version and have unique codes/order.
- Assessment maximum points must be greater than zero; grade values must later remain within the assessment range.
- Assessments declare required/optional status, kind, position, and active state.
- Draft configuration is editable; approved configuration is locked and can only be replaced by a new version.
- Approval validates endpoint ownership, active PO-set compatibility, positive measurement definitions, and required metadata.
- Deleting or mutating a referenced syllabus is prohibited; draft-only unused records may be removed.

## Acceptance criteria

- [ ] Authorized instructors can create a draft syllabus with LOs and assessments.
- [ ] Invalid points, duplicate codes, and cross-syllabus references are rejected.
- [ ] Approval locks the version and records approver/time.
- [ ] A revision creates a new version while preserving the prior version.
- [ ] An offering cannot calculate official scores from an unapproved incompatible syllabus.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

