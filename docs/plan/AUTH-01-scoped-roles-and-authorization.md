# AUTH-01 — Scoped roles and authorization

**Blocked by:** BOOT-01.

## User story

As an institution, I can assign users roles scoped to a program or course offering, so every record and action is protected by least privilege.

## Rules

- Roles are assignments, not global booleans: administrator, coordinator, instructor, teaching assistant, student, and optional auditor.
- A user may hold different roles in different programs or offerings.
- Deny by default. Enforce scope in queryset/selector filtering, service methods, serializers, exports, and direct-object lookups.
- Students can read only their own released grades and published outcomes.
- Instructors/TAs can read and mutate only assigned offerings, subject to delegated permissions.
- Coordinators can manage their assigned program; administrators can manage institution-wide records.
- Role changes and sensitive access/export actions produce immutable audit events.
- Unauthorized hidden objects may return 404; visible but forbidden actions return 403, consistently.

## Acceptance criteria

- [ ] Cross-student and cross-offering object-reference tests fail safely.
- [ ] A coordinator cannot access another program's draft or grades.
- [ ] An instructor cannot mutate an unassigned offering.
- [ ] A student cannot access unreleased grades, faculty previews, or another student's evidence.
- [ ] Role assignment, revocation, and sensitive exports are audited.
