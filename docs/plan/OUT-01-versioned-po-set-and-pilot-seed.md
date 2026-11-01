# OUT-01 — Versioned PO set and pilot seed

**Blocked by:** ACAD-01.

## Epic and PRD traceability

- **Epic:** [EPIC-02](epics/EPIC-02-academic-catalog.md)
- **PRD:** PRD §3; §11.1
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a coordinator, I can create and activate a versioned set of eleven program outcomes, so every syllabus and published score has stable outcome semantics.

## Rules

- A PO set belongs to one program and has a unique version, status, effective date, and source reference.
- The pilot seed contains exactly PO1 through PO11, ordered and uniquely coded within the set.
- Each outcome requires a complete display label, authoritative description, source URL/reference, and ordering.
- Draft sets can be edited; activated sets and their outcomes are immutable.
- Changing meaning, wording, numbering, or ordering creates a new PO-set version rather than overwriting history.
- An offering syllabus must bind to one PO-set version; historical scores retain that version.
- Activation requires coordinator/admin authority and an effective date; only one active set applies for a program/date policy.

## Acceptance criteria

- [ ] A seeded program displays all eleven ordered pilot POs.
- [ ] Draft validation rejects duplicate codes, missing descriptions, invalid ordering, and incomplete source metadata.
- [ ] Activation prevents in-place mutation and records the actor/time.
- [ ] A new version leaves old syllabus and publication references unchanged.
- [ ] Users cannot silently combine scores from different PO semantics.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

