# Reports UI

`@outcometrik/reports` owns report features for published outcome results.

- `features/exports/` — CSV/PDF report export client and download helper. It follows the
  draft [EXP-01 export contract](../../../../docs/plan/EXP-01-contract.md). Authorization,
  publication state and the audit trail are enforced by the server, never by this module.

The export endpoint is not implemented on the server yet (it depends on the publication
and analytics stories), so the client is tested against stubbed responses.
