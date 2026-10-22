# OUT-01 — Versioned PO set and pilot seed

**Blocked by:** ACAD-01.

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
