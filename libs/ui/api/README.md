# UI API SDK

Import shared API primitives from `@outcometrik/api`. This framework-independent workspace library owns `request<T>()`, `RequestOptions`, `ApiError`, error kinds, pagination, validation errors, and common wire types (UUID, UTC timestamp, decimal string, nullable score).

The transport standardizes same-origin credentials, JSON serialization, CSRF headers, cancellation, timeout, and HTTP error handling. It has no React or TanStack Query dependency. `request<T>()` describes a wire response; endpoint clients must validate server data before returning it to the UI.

Keep endpoint-specific behavior with its feature: `apps/web/lib/health/` uses this SDK to call and validate the health endpoint. Import the SDK public entry point rather than its internal files, and reuse its types instead of defining competing transport contracts.

```ts
import { request } from '@outcometrik/api';
import type { Page, UUID } from '@outcometrik/api';
```

Run `pnpm nx test ui-api`, `pnpm nx lint ui-api`, and `pnpm nx run ui-api:typecheck`. The package exports TypeScript source for workspace consumers; it does not require a separate publishing or build step.
