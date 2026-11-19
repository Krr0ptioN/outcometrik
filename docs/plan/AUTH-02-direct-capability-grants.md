# AUTH-02 — Scope-bound direct capability grants

**Blocked by:** AUTH-01.
**Estimate:** To be estimated by the team.
**Owner/reviewer:** Unassigned; decide at planning based on capacity and skills.

## Epic and PRD traceability

- **Epic:** EPIC-01.
- **PRD:** PRD §3; §11.1 AUTH-01.
- **Out of scope:** No broader permissions, external SIS/LMS, or unapproved policy defaults.

## User story

As a Administrator, I want to grant an individual capability to a user within a named program or offering scope, so that I can delegate one action without changing the user role or widening unrelated access.

## Acceptance criteria

- **Scenario:** Given a user has no role granting Edit Grades and an administrator grants Edit Grades for offering A, When the user edits offering A and then attempts offering B, Then the first action is allowed and the second is denied. Revocation removes the grant unless another applicable grant remains.

## Contracts and validation

Honor API/domain ownership, scoped authorization, explicit null/error states, and current revisions. Validate input at the boundary and reauthorize writes server-side.

## Implementation tasks

- [x] Grant/revoke persistence; scope-aware policy evaluation; audit actor/action/scope; authorization tests for overlap and revocation.
- [x] Add focused automated tests for success, failure, and scope denial.
- [x] Document contract and update dependent stories.

## Completed implementation & contract

- **Exact-scope policy rule (`libs/modules/access/access/policy.py`)**:
  - `AuthorizationService.scope_ids` and `AuthorizationService.scope_filter` treat `RoleAssignment` as hierarchical (inheriting down `institution -> program -> offering`), while `DirectCapabilityGrant` is strictly exact-scope (`Q(pk__in=exact)` only, with zero program-to-offering inheritance).
- **Audited grant and revocation (`libs/modules/access/access/services.py` & `api.py`)**:
  - `POST /api/access/assignments/` accepts `capability` (single capability code) or `capabilities` (non-empty list of unique capability codes) scoped to a specific `Scope` UUID and guarded by `access.manage` on the target scope.
  - `DELETE /api/access/grants/<UUID>/` revokes an active `DirectCapabilityGrant` (setting `revoked_at` idempotently under `select_for_update` lock) when the actor holds `access.manage` on the grant's scope; out-of-scope grants return `404`.
  - Every new grant appends an immutable `AuditEvent` (`action="capability.granted"`) and every revocation appends `action="capability.revoked"` with actor, subject, scope, and assignment metadata in the same transaction.
- **Instructor workspace & queryset scoping integration (`apps/api/academic/`)**:
  - `WorkspaceService.instructor_offerings` (`apps/api/academic/services/workspaces.py`) authorizes users who hold either an active `instructor` role assignment OR an active offering-scoped `DirectCapabilityGrant` for any offering/instructor capability (`"grades.view"`, `"grades.edit"`, `"grades.release"`, `"offering.manage"`, `"syllabus.draft"`), unioning offering IDs from both sources.
  - `scope_offerings` (`apps/api/academic/scoping.py`) unions offering IDs across `("offering.manage", "grades.view", "grades.edit", "grades.release", "syllabus.draft")` (plus student enrollments) so offering detail/list endpoints resolve for direct capability holders without requiring a full role assignment.
  - `scope_enrollments` (`apps/api/academic/scoping.py`) unions offering IDs across `("grades.view", "grades.edit", "grades.release", "offering.manage")` (plus the student's own enrollment rows) so direct `grades.edit` or `offering.manage` holders can view the offering roster and enter grades.

## Verification

```bash
uv run --directory apps/api ruff check . ../../libs/modules/access
uv run --directory apps/api ruff format --check . ../../libs/modules/access
POSTGRES_DB=outcometrik_auth_02 POSTGRES_USER=outcometrik POSTGRES_PASSWORD=outcometrik POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 uv run --directory apps/api python manage.py check
POSTGRES_DB=outcometrik_auth_02 POSTGRES_USER=outcometrik POSTGRES_PASSWORD=outcometrik POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432 uv run --directory apps/api pytest
```
