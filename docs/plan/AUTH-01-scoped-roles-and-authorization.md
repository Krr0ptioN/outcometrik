# AUTH-01 — Scoped roles and authorization

**Blocked by:** BOOT-01.

## Epic and PRD traceability

- **Epic:** [EPIC-01](epics/EPIC-01-foundation-identity.md)
- **PRD:** PRD §3; §11.1 AUTH-01
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As an institution, I can assign users roles scoped to a program or course offering, so every record and action is protected by least privilege.

## PRD v2 scope

Roles bundle capabilities. Administrators may grant individual capabilities directly to a user for a specific scope without changing the role. Direct grants do not widen access beyond that scope. Required role set is Administrator, Program Coordinator, Instructor, Student.

## Rules

- Roles are assignments, not global booleans: administrator, program coordinator, instructor, and student.
- A user may hold different roles in different programs or offerings.
- Deny by default. Enforce scope in queryset/selector filtering, service methods, serializers, exports, and direct-object lookups.
- Students can read only their own released grades and published outcomes.
- Instructors can read and mutate only assigned offerings, subject to delegated permissions.
- Coordinators can manage their assigned program; administrators can manage institution-wide records.
- Role and direct-capability grants/revocations and sensitive export actions produce immutable audit events.
- Unauthorized hidden objects may return 404; visible but forbidden actions return 403, consistently.

## Acceptance criteria

- [ ] Cross-student and cross-offering object-reference tests fail safely.
- [ ] A coordinator cannot access another program's draft or grades.
- [ ] An instructor cannot mutate an unassigned offering.
- [ ] A student cannot access unreleased grades, faculty previews, or another student's evidence.
- [ ] Role/direct-capability assignment and revocation, and sensitive exports, are audited.
- [ ] A direct grant authorizes only its named action and scope, and revoking it removes that access unless another applicable grant remains.

## Implementation tasks

- [ ] Confirm API/data contract and authorization scope against the owning domain module.
- [ ] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [ ] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [ ] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [ ] Update API/UI documentation and verify downstream stories remain compatible.

## Implemented backend contract

See [API authorization documentation](../../apps/api/README.md#scoped-authorization-auth-01)
for the assignment/revocation endpoints, role matrix, bootstrap procedure, and
selector/service integration contract. The `access` application implements the
centralized policy described in `deep-research-report(2).md`, with database-backed
scope ancestry and exact-scope direct grants. Its tests cover the acceptance
matrix using a protected-record fixture because academic, grade, evidence, and
outcome models/endpoints have not been introduced yet. Those domains must consume
the shared selectors and service checks when implemented. The institution dashboard at `/admin` now provides account creation, role and
direct-grant management, program/offering setup and audit activity. Session
sign-in is available at `/login`.
