# EXP-01 — Outcome score report exports

**Blocked by:** ANA-01.

## Epic and PRD traceability

- **Epic:** [EPIC-06](epics/EPIC-06-outcomes-and-reports.md)
- **PRD:** PRD §§7, 11.5
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an authorized user, I can download a reproducible CSV or PDF report for my permitted scope, so outcome results can be reviewed and shared without changing source data.

## Rules

- Exports identify publication/run, program, term, PO-set version, generated time, scope, sample size, coverage, and policy version.
- Student exports contain only that student's released published data; faculty/coordinator exports follow their assigned offering/program scope.
- Reports show null/Not assessed and incomplete states distinctly from numeric zero.
- Evidence exports preserve the formula path, source revisions, weights, numerator, denominator, and intermediate values where authorized.
- CSV cells beginning with `=`, `+`, `-`, or `@` are escaped to prevent spreadsheet formula injection.
- Export generation is read-only and reproducible from immutable publication data; failed PDF generation must not affect the publication.
- Large exports are bounded, authorized, audited, and may be delivered as a job when measured latency requires it.

## Acceptance criteria

- [ ] Authorized CSV and PDF exports match the selected immutable publication.
- [ ] Unauthorized scope and unpublished data never appear in an export.
- [ ] Null, incomplete, exempt, and zero states are preserved.
- [ ] CSV formula injection safeguards and export audit events are tested.
- [ ] Re-running an export for the same publication produces equivalent content.
## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

