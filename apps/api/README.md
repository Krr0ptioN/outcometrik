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

## Academic structure API (ACAD-01)

Base path `/api/v1`. All routes need authentication. Reads are scoped to what the user teaches
or attends; writes are staff-only until AUTH-01 replaces `academic/permissions.py`. Lists are
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
- Change enrollment status with `PATCH /enrollments/{id}/` and `{"status": "...", "reason": "..."}`.
  Each change is recorded in `EnrollmentStatusEvent`.
- Eligibility is decided by `academic/policy.py` (`proposed-v1`: enrolled and completed count,
  withdrawn and incomplete do not). The policy version is stored on each enrollment.
- `input_revision` on programs and offerings increases when an eligible offering or enrollment
  is added, or when a status change flips eligibility. Calculations use it to detect stale input.

Downstream stories should read rosters through `academic.selectors.eligible_roster(offering)`.
