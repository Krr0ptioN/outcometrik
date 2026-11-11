# Outcometrik web

Next.js/React frontend with TanStack Query, Tailwind CSS, and a source-owned shadcn/ui button. `components.json` configures future components.

## Development

Run `pnpm install --frozen-lockfile` and `pnpm prepare:api`. Start the database, Redis, and API with `./tools/compose-up.sh`, then run `pnpm dev:web` and open http://localhost:3000. Alternatively use `pnpm dev:api` with a configured database.

Browser requests use `/api/health/status` on the web origin. Next rewrites `/api/*` to `API_UPSTREAM` (default `http://127.0.0.1:8000`). Copy `.env.example` to `.env.local` to override before building.

## Contracts

`@outcometrik/api` (`libs/ui/api`) provides the shared SDK: `request<T>()`, `ApiError`, pagination, and wire types for UUIDs, UTC timestamps, decimal strings, and nullable scores. Errors distinguish unauthorized, forbidden, validation, conflict, unavailable, and unexpected responses. Validation payloads remain in `details`; endpoint-specific responses need runtime validation, as implemented by `@outcometrik/system` (`libs/ui/modules/system/src/features/health/`), which consumes the SDK and owns the health endpoint contract. Requests time out after ten seconds and honor cancellation.

Requests use same-origin session cookies. Mutations require a Django `csrftoken` cookie or explicit token and send `X-CSRFToken`. AUTH-01 must establish this token before mutations. DRF session authentication may return 403 for unauthenticated users. The server owns authorization, scoring, and publication.

The pilot HTTPS ingress must route `/api/*` to Django and other paths to the frontend. Enable secure session/CSRF cookies on the production API and trust only the public origin for CSRF. Verify production routing, including OpenNext/Cloudflare; the Next rewrite supports local development.

## Checks

```sh
pnpm nx run web:typecheck
pnpm nx lint web
pnpm nx test web
pnpm nx build web
pnpm exec playwright install chromium
pnpm nx e2e web
```

Tests cover API errors, credential and CSRF handling, loading, retry, empty workspace, and keyboard navigation. CI runs type checking and build explicitly.

Project identifiers use `outcometrik`, including database defaults, Compose project, image names, and Worker name. Existing installations should explicitly retain their previous Compose project name and database/user environment settings until data is migrated. Renaming defaults does not migrate existing volumes or deployed resources.

## Institution administration

Visit `/login` to sign in with a Django account. Institution administrators are
sent to `/admin`; coordinators, instructors, and students go to their role view.
The workspace home and session menu let multi-role users switch dashboards. The admin dashboard is the
institution view: overview, people/access, programs/course offerings, and audit
activity. It supports account creation with an initial scoped role, additional
role/direct-capability assignments, and revocations. Search and pagination are
server-backed; every request is authorized by Django. No browser token storage is
used, and signing out clears the query cache.

Create an initial Django user and run the API's `bootstrap_access` command with
the institution name. Provision departments, terms, courses, programs and
offerings through the academic API; those records create their matching access
scopes automatically. The dashboard can then create coordinators, instructors
and students with scoped roles. See [the API guide](../api/README.md) for
endpoint details, password rules and CSRF configuration.

Coordinator views show academic rosters, instructor views show assigned offering
rosters, and students see their own courses. Grade entry and published outcome
profiles depend on gradebook and outcome records planned separately.

`pnpm nx e2e web` runs a disposable SQLite-backed API using
`tools/auth-e2e-server.py` alongside the production Next server. It requires the
API's uv environment and port 8000 to be available. The test account exists only
in a temporary database that is removed after the server stops.
