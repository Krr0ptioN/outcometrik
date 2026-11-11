# EXP-01 — Report export API contract (draft)

Status: **draft prototype contract.** The publication, analytics and calculation stories
([CALC-03](CALC-03-publication-stale-version-protocol.md), [ANA-01](ANA-01-cohort-analytics.md))
are not implemented yet. This contract is what the export UI is built against; the server
side adopts or adjusts it when those stories land. Product rules live in
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
| `5xx`  | Generation failed (for example PDF rendering). The publication is not affected |

Unauthorized scope and unpublished data must never appear in a response body, including error bodies.

## Not in this prototype

- Large exports delivered as a job (`202` with a status URL) when measured latency requires it. Clients should treat any `2xx` other than `200` as unsupported until that is specified.
- Server-side generation, authorization and audit events. The UI treats the server as authoritative; the audit event name proposed for it is `export.generated`.
