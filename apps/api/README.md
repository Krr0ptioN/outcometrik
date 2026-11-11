# API

Django REST Framework API managed with uv. The runtime uses PostgreSQL and Redis through the repository Compose stack.

```sh
pnpm nx run api:sync
pnpm nx serve api
```

For a complete local database-backed stack:

```sh
./tools/compose-up.sh
```

To start only PostgreSQL and Redis for running Django on the host, copy
`.env.example` to `.env`, set a local `POSTGRES_PASSWORD`, and run
`./tools/compose-dependencies-up.sh`. `pnpm nx serve api` reads the same `.env`
so Django connects to PostgreSQL on `localhost`. The database and Redis ports
bind to `127.0.0.1`; persistent database data uses the `postgres-data` volume.
Stop the services with `docker compose -f infra/compose.dependencies.yaml down`.

The only health endpoint is `/api/health/status`. It returns only `{ "status": "ok" }` or `{ "status": "unavailable" }`; dependency details are intentionally not exposed. For isolated local tests without PostgreSQL, set `DJANGO_DB_ENGINE=django.db.backends.sqlite3`.

## Scoped authorization (AUTH-01)

The `access` Django application in `libs/modules/access` follows `deep-research-report(2).md`: session
identity, one server-side capability policy, scoped role assignments, exact-scope
direct grants, filtered selectors, and transactional audits. Django staff and
superuser flags do not confer domain access. JWT and external policy engines are
outside this slice. The institution dashboard is available at `/admin`, with sign-in at `/login`.
Academic/grade workflows remain separate from this administration surface.

Run migrations, create an active user, then initialize the first institution.
Use the management wrapper so commands load the same root `.env` as Compose and
`pnpm nx serve api`:

```sh
./tools/manage-api.sh migrate
./tools/manage-api.sh createsuperuser
./tools/manage-api.sh bootstrap_access USERNAME --name "Your institution"
```

This trusted-operator command prints the institution scope UUID, creates an
audited administrator assignment, and refuses to run after scopes exist. Domain
provisioning must create a program scope under its institution and an offering
scope under its program. Scope IDs are authoritative stored relationships, not
client-supplied ancestry; changing ancestry is unsupported. Only trusted domain
provisioning code may write scope models, and must use `Scope.save()` validation.
Do not use bulk writes or raw SQL to change scopes or access assignments.

Role defaults:

| Role                | Scope                       | Capabilities                                                                                    |
| ------------------- | --------------------------- | ----------------------------------------------------------------------------------------------- |
| Administrator       | Institution and descendants | All registered capabilities, including access management                                        |
| Program Coordinator | Program and descendants     | Program/offering management, grade view/edit/release/export, outcomes/evidence, faculty preview |
| Instructor          | Assigned offering           | Offering management, grade view/edit, outcomes/evidence, faculty preview                        |
| Student             | Assigned offering           | Own released grades/evidence and own published outcomes                                         |

Users can hold different assignments in different scopes. Direct grants authorize
only the named capability at the exact scope; they do not inherit. Explicit
read grants confer the named read capability, whereas the student role alone
always requires ownership and release/publication. Revocations are immediate;
no authorization decisions are cached.

Authenticated same-origin APIs (session cookie and CSRF token required on writes):

- `POST /api/access/assignments/`: `{ "user": <user PK>, "scope": "<UUID>",
"role": "instructor" }`, or replace `role` with `capability`, e.g. `grades.edit`.
  Returns `201 { "id": "<assignment UUID>" }`. Exactly one role/capability is
  required. The actor must have `access.manage` in that scope.
- `DELETE /api/access/roles/<UUID>/` and `/api/access/grants/<UUID>/`: audited,
  idempotent revocation; returns 204. Assignments outside administrable scopes
  return 404. Forbidden creation/actions return 403; invalid input returns 400.

Use `access.services.assign` and `revoke` for all runtime assignment mutations.
Use `authorization.require(principal=actor, capability=..., scope=record.scope,
resource=ResourceContext(...))` inside domain mutation services, using scope and
resource facts from the stored record. Select list/detail querysets with
`visible_resources` / `visible_resource` before serialization. Their resource
contract is a `scope` FK plus `owner_id`, `released`, and `published` fields;
domain-specific adapters must map their schema to this contract. The DRF
`HasCapability` adapter requires `required_capability` and a `resource_context`
method on the view. It supplements selector and service checks; list checks
alone do not perform object authorization. Hidden objects return 404; a forbidden
action on a visible object returns 403.

Use `sensitive_export` with a stored scope, queryset and eager serializer; it
filters to that scope and visible records and appends an audit event before
returning. Serializers must produce a materialized payload, without sending or
streaming it inside the callback. Audit failure rolls back assignment changes or
prevents the export from returning. Audit events reject updates/deletes through
the ORM and PostgreSQL/SQLite triggers. Database owners can disable triggers;
operational database privileges must protect against that separately.

Verification:

```sh
DJANGO_SECRET_KEY=test DJANGO_DB_ENGINE=django.db.backends.sqlite3 uv run pytest
uv run ruff check . ../../libs/modules/access
uv run ruff format --check . ../../libs/modules/access
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
```

The authorization tests also run against PostgreSQL in the existing CI test job.

## Authentication and institution dashboard

`GET /api/auth/session/` returns `{user, scopes}` and sets the CSRF cookie,
including for anonymous visitors (`user: null`). `POST /api/auth/login/` accepts
`username` and `password`; `POST /api/auth/logout/` ends the session. Both writes
require a valid CSRF cookie/header, including anonymous login. Login rotates the
session and CSRF token. Invalid or inactive accounts receive the same error.
Login is throttled to 10 attempts/minute per client using the configured Django
cache (the default local-memory cache applies per process). Session and dashboard
responses use `Cache-Control: no-store`.

Configure `DJANGO_CSRF_TRUSTED_ORIGINS` as a comma-separated list of web origins
when using the Next.js proxy. Development defaults permit `localhost:3000` and
`127.0.0.1:3000`; production must set its actual HTTPS web origin. Next preserves
API trailing slashes so Django endpoints are reached without redirects.

Institution administrators can use:

- `GET /api/access/dashboard/?scope=<institution UUID>&search=<text>&page=1`:
  institution statistics, programs/offerings, paginated people (20/page), scoped
  roles/direct grants, the capability catalog, and the latest 20 audit events.
  Institution access is checked before any records are returned. Cross-institution
  assignments and events are excluded even for users shared by institutions.
- `POST /api/access/accounts/`: `username`, `email`, `first_name`, `last_name`,
  `password`, `role` (slug), and `scope` (UUID). Requires access management in the
  target scope. Passwords are hashed and checked against Django's password policy.
  Account, institution membership, initial role and audit events commit together.
  Only the allowed input fields are accepted; staff/superuser flags are never set.
Academic programs and offerings are created through the academic API so every access scope is
linked to a real academic record. The access API does not create standalone program/offering
scopes.

Institution membership persists independently of active assignments. Removing a
person's last role removes their permissions but keeps their account visible to
institution administrators so access can be restored. The last active
administrator assignment in an institution cannot be revoked until another
active administrator is assigned. Initial passwords should be delivered through
the institution's secure account-provisioning channel; there is no public signup
or automated invitation/password-recovery email in this implementation.

## Academic structure API (ACAD-01 + AUTH-01)

Base path `/api/v1`. All routes need authentication. Academic institution, program, and offering
UUIDs are also the corresponding access-scope UUIDs. A data migration creates these links for
existing records. Institution scopes are established by trusted bootstrap; new institutions must
be provisioned against an existing institution scope. Reads filter by access roles and grants,
and writes enforce the required capability against the record's stored parent scope. Lists are
paginated (`page`, `page_size`, default 50, max 200) and filterable by query parameter.

| Route | Methods | Filters |
|---|---|---|
| `/institutions/` | GET, POST, GET/PATCH `{id}` | `code` |
| `/departments/` | same | `institution`, `code` |
| `/programs/` | same | `department`, `status`, `code` |
| `/terms/` | same | `institution`, `year`, `season` |
| `/courses/` | same | `home_department`, `code`, `active` |
| `/program-courses/` | same | `program`, `course`, `status` |
| `/program-memberships/` | same | `program`, `user`, `status` |
| `/offerings/` | same | `program`, `course`, `term`, `section`, `status` |
| `/offerings/{id}/enrollments/` | GET, POST | roster of one offering |
| `/instructor-assignments/` | same | `offering`, `user`, `assignment_role` |
| `/enrollments/` | GET, POST, GET `{id}` | `offering`, `student`, `status`, `eligible_for_outcomes` |

Rules:

- There is no DELETE. Archive with `PATCH {"status": "archived"}`. Model `delete()` raises.
- Identity fields (for example an offering's program, course and term) cannot be changed.
- Duplicates return `400`. An offering needs an active program and an `approved` program-course
  link, otherwise `400`.
- A student must hold an active program membership to be enrolled.
- A student must also have an active student role assignment on that offering. Instructor
  assignments create the matching instructor role through the audited access assignment service.
- Program coordinators can manage their assigned program and descendant offerings. Instructors
  are limited to their assigned offerings. Students see only their own enrollment rows.
- Cross-scope detail lookups are filtered before object resolution and return 404. Writes require
  `access.manage`, `program.manage`, `offering.manage`, or `grades.edit` on the relevant scope.
- Change enrollment status with `PATCH /enrollments/{id}/` and `{"status": "...", "reason": "..."}`.
  Each change is recorded in `EnrollmentStatusEvent`.
- Eligibility is decided by `academic/policy.py` (`proposed-v1`: enrolled and completed count,
  withdrawn and incomplete do not). The policy version is stored on each enrollment.
- `input_revision` on programs and offerings increases when an eligible offering or enrollment
  is added, or when a status change flips eligibility. Calculations use it to detect stale input.

Downstream stories should read rosters through `academic.selectors.eligible_roster(offering)`.

## Role workspaces

`GET /api/auth/session/` includes active role assignments with their scope. The web home page
offers every dashboard assigned to the signed-in user; login defaults prioritize institution
admin, coordinator, instructor, then student.

- `GET /api/v1/workspaces/coordinator/` returns only programs where the actor has
  `program.manage`, plus program memberships and offering enrollment counts.
- `GET /api/v1/workspaces/instructor/` returns instructor-assigned offerings and their authorized
  rosters. An exact `grades.view` grant can add its named offering.
- `GET /api/v1/workspaces/student/` returns only the signed-in student's own enrollments.

These responses use `Cache-Control: no-store`. Gradebook and published PO records are not yet part
of the academic schema; the student workspace reports no published outcomes until those records
are implemented. The instructor workspace currently provides the assigned course roster, not grade
entry.
