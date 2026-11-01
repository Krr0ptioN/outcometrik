# UI-03 — Student PO profile and explanation

**Blocked by:** CALC-02, BOOT-02.

## Epic and PRD traceability

- **Epic:** [EPIC-07](epics/EPIC-07-quality-demo-delivery.md)
- **PRD:** PRD §§6, 11.5 FR-501–504
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a student, I can view my released PO1–PO11 profile and inspect why each value exists, so attainment is understandable without exposing private data.

## Rules

- Always show all eleven PO codes; unassessed values are null/“Not assessed,” never zero.
- Show score, coverage, status, term/snapshot selector, PO-set version, publication identity, and freshness.
- Only released grades and published snapshots are eligible for student display.
- Drill-down follows publication evidence: student → course → LO → assessment → normalized grade/weight.
- Do not resolve historical evidence from mutable current grade rows.
- Unauthorized IDs, publication guesses, and another student's profile return safe 404/403 behavior.
- Charts require accessible data tables, explicit 0–100 axes, text statuses, and non-color-only distinctions.

## Acceptance criteria

- [ ] A student sees all eleven outcomes with correct null/status behavior.
- [ ] The canonical values and evidence path are visible for an authorized publication.
- [ ] A grade correction makes the current result stale without rewriting history.
- [ ] Direct-object and URL-manipulation tests cannot expose another student.
- [ ] Keyboard and non-visual users can read the same profile data.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

