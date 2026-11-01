# BOOT-02 — Bootstrap the React frontend and typed API client

**Blocked by:** BOOT-01.

## Epic and PRD traceability

- **Epic:** [EPIC-01](epics/EPIC-01-foundation-identity.md)
- **PRD:** PRD §11.6
- **Scope:** MVP story; optional v1 features are excluded unless PRD v2 explicitly includes them.

## User story

As a user, I can open the web application and see whether the API is available, so the frontend foundation is usable before domain screens are built.

## Rules

- Use React/TypeScript, Next.js, TanStack Query, shadcn/ui, and Tailwind CSS as specified by the PRD.
- Serve the frontend and API from one public origin for the pilot; mutations use secure session cookies and CSRF protection.
- API types must represent UUIDs, UTC timestamps, decimal values as strings, nullable scores, pagination, validation errors, and `409 Conflict` responses.
- Loading, empty, unavailable, unauthorized, and validation states must be explicit and accessible.
- The browser is never the authority for permissions, score calculations, or publication state.

## Acceptance criteria

- [x] A clean checkout starts the frontend and calls the API health endpoint.
- [x] The client exposes typed request/response helpers and consistent error handling.
- [x] API unavailable and unauthorized states render without uncaught exceptions.
- [x] A keyboard-accessible shell and navigation placeholder are present.
- [x] The frontend build and type check pass locally and in CI.
## Implementation tasks

- [X] Confirm API/data contract and authorization scope against the owning domain module.
- [X] Implement the smallest vertical slice that satisfies the acceptance criteria.
- [X] Add focused unit/integration coverage for success, invalid input, and denied scope.
- [X] Integrate the UI states and accessible error/empty/loading behavior when the story has a UI surface.
- [X] Update API/UI documentation and verify downstream stories remain compatible.

