# Access UI

`@outcometrik/access` owns session authentication and institution administration.
Public components are `SignIn`, `SessionMenu`, and `AdminDashboard`. Routes and navigation
composition remain in `apps/web`.

Session and dashboard clients validate wire responses and use `@outcometrik/api`
for same-origin credentials, cancellation, CSRF and normalized errors. TanStack
Query owns server state. Institution scope/search/page are part of dashboard query
keys; mutations invalidate dashboard/session data. Session changes clear the
cache. The server remains authoritative for all permissions.

Run the `ui-access` Nx lint, test and typecheck targets. The web browser tests
exercise login, program/offering setup, student/instructor account creation,
assignment/revocation, logout and student denial against a disposable real API.

The UI composes shared shadcn primitives from `@outcometrik/ui`; it does not own
parallel styled controls. The global application theme supplies semantic colors.
