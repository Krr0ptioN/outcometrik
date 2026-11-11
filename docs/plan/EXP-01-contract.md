# EXP-01 — Report export API contract (draft)

Status: **draft prototype contract.** The publication, analytics and calculation stories
([CALC-03](CALC-03-publication-stale-version-protocol.md), [ANA-01](ANA-01-cohort-analytics.md))
are not implemented yet. The export UI and the API's export layer (`apps/api/reports`) are
built against this contract; a real publication reader replaces the placeholder when those
stories land. Product rules live in
[EXP-01](EXP-01-score-report-exports.md) and PRD §§7, 11.5.

## Endpoint

`GET /api/v1/reports/exports/`

Export generation is read-only and never changes a publication.

| Query parameter  | Required            | Values                                                                                         |
| ---------------- | ------------------- | ---------------------------------------------------------------------------------------------- |
| `publication_id` | yes                 | UUID of an immutable publication                                                               |
| `format`         | yes                 | `csv` or `pdf`                                                                                 |
| `scope`          | yes                 | `student` (the signed-in student's own data) or `cohort`                                       |
| `program_id`     | `cohort` scope only | UUID of a program. Not accepted for `student`; the server derives the student from the session |

## Success

`200 OK`, body is the file.

| Header                | Value                                                |
| --------------------- | ---------------------------------------------------- |
| `Content-Type`        | `text/csv; charset=utf-8` or `application/pdf`       |
| `Content-Disposition` | `attachment; filename="<generated name>.<csv\|pdf>"` |
| `Cache-Control`       | `no-store`                                           |

Re-requesting the same publication, scope and format returns equivalent content.

## Errors

Errors use the existing JSON error shape and the status conventions in the
[design doc](../design/outcometrik.md).

| Status | Meaning                                                                        |
| ------ | ------------------------------------------------------------------------------ |
| `400`  | Invalid or missing query parameter, or a parameter not allowed for the scope   |
| `401`  | Not signed in                                                                  |
| `403`  | The publication or scope is visible but export is not permitted for this user  |
| `404`  | Publication does not exist, is unpublished, or is hidden from this user        |
| `413`  | The export is larger than the synchronous bound (`REPORT_EXPORT_MAX_ROWS`)     |
| `503`  | Generation failed (for example PDF rendering). The publication is not affected |

Unauthorized scope and unpublished data must never appear in a response body, including error bodies.
`403` means the user has no access of the requested kind at all (for example a student asking for a
cohort report). A program or publication the user cannot see is a `404`, identical to one that does
not exist.

## Authorization

Export access follows on-screen access (PRD §11.5), using the existing capabilities, with no new ones:

- `student` scope: the requester must hold a student role; the server always exports the requester's
  own report and never accepts a student identifier. Needs `outcomes.view` on an offering they are
  enrolled in. Evidence is included only where `evidence.view` also applies.
- `cohort` scope: `outcomes.view` on the program (inherited from institution or program roles, or an
  exact direct grant). Evidence is included only with `evidence.view`.
- Faculty (instructor) exports at offering level are not supported yet: the contract has no offering
  parameter. Instructors receive `404` for program-level reports.

## Content

- Both formats identify the publication and run, program, term, PO-set version, calculation policy
  version, scope, population, sample size, coverage, freshness, publication time and generation time.
- Scores are rounded to one decimal (`ROUND_HALF_UP`) only here, from full-precision values. Evidence
  numerators, denominators, weights and intermediate values keep full precision.
- A missing value is never zero: CSV has a blank Score plus an explicit State (Not assessed,
  Incomplete, Exempt, Unmapped); PDF shows an em dash and the State. A measured zero is `0.0`.
- CSV is UTF-8 with a BOM and CRLF line ends. Text cells starting with `=`, `+`, `-`, `@`, tab, CR or
  LF are prefixed with `'` so spreadsheets cannot run them as formulas.
- Each successful export writes an audit event, `reports.exported`, holding identifiers, format, row
  count and size only. Rendering a file changes nothing else, so a failed PDF cannot affect a
  publication, and the same publication re-exports to equivalent content.

## Not in this prototype

- Large exports delivered as a job (`202` with a status URL) when measured latency requires it. Clients should treat any `2xx` other than `200` as unsupported until that is specified.
- A real publication reader. Until CALC-03/ANA-01 provide one, the API answers every export with `404`.
