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

The only health endpoint is `/api/health/status`. It returns only `{ "status": "ok" }` or `{ "status": "unavailable" }`; dependency details are intentionally not exposed. For isolated local tests without PostgreSQL, set `DJANGO_DB_ENGINE=django.db.backends.sqlite3`.

## Scoped authorization (AUTH-01)

The `access` Django application in `libs/modules/access` follows `deep-research-report(2).md`: session
identity, one server-side capability policy, scoped role assignments, exact-scope
direct grants, filtered selectors, and transactional audits. Django staff and
superuser flags do not confer domain access. JWT and external policy engines are
outside this slice. No academic/grade models or frontend assignment screen exist
yet; this module supplies their authorization boundary.

Run migrations, create an active user, then initialize the first institution:

```sh
uv run python manage.py migrate
uv run python manage.py bootstrap_access USERNAME
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
