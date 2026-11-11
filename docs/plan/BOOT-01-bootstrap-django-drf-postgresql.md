# BOOT-01 — Bootstrap Django, DRF, and PostgreSQL

**Blocked by:** None — can start immediately.

## Epic and PRD traceability

- **Epic:** [EPIC-01](epics/EPIC-01-foundation-identity.md)
- **PRD:** PRD §11.6
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a developer, I can start the API against PostgreSQL and verify its readiness, so later domain slices have a reliable runtime foundation.

## Rules

- Use Python 3.13, Django 5.2, Django REST Framework, PostgreSQL 16+, and environment-managed settings.
- Local development must have a one-command database/application bootstrap and deterministic migrations.
- `/api/health/status` is the only public health route. It checks that the service can query its database but exposes only `status: ok` or `status: unavailable`.
- Health responses must not expose secrets, grade data, credentials, or connection details.
- API errors use JSON consistently without exposing dependency names, connection details, or internal stack traces.
- Store timestamps in UTC and use UUIDs for business entities.
- Keep database credentials and application secrets out of source control.

## Acceptance criteria

- [x] A clean checkout can migrate PostgreSQL and start Django successfully.
- [x] `GET /api/health/status` returns only the minimal status payload and uses `503` when the database check fails.
- [x] A database outage makes `/api/health/status` return only `{"status":"unavailable"}` with HTTP 503.
- [x] A smoke test verifies the minimal response and absence of dependency details.
- [x] CI exercises the API test suite against PostgreSQL 16.
## Implementation tasks

- [X] Confirm API/data contract and authorization scope against the owning domain module.
- [X] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [X] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [X] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [X] Update API/UI documentation and verify downstream stories remain compatible.

