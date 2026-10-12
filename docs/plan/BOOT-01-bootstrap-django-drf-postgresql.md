# BOOT-01 — Bootstrap Django, DRF, and PostgreSQL

**Blocked by:** None — can start immediately.

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
