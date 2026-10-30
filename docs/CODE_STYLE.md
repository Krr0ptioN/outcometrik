# Code style and frontend architecture

This guide defines repository conventions. Frontend modules group related product capabilities; individual features are implementation units within a module.

## Ownership and layout

```text
apps/web/                         # Next.js routes, app composition, root providers
libs/ui/core/                     # Shared UI primitives: @outcometrik/ui
libs/ui/api/                      # Shared transport and wire types: @outcometrik/api
libs/ui/modules/
  <module>/                      # @outcometrik/<module>, Nx ui-<module>
    package.json
    project.json
    tsconfig.json
    eslint.config.mjs
    vitest.config.ts
    src/
      index.ts                   # Explicit supported public exports
      features/
        <feature>/
          index.ts
          api.ts
          types.ts
          components/
          hooks/
          <feature>.test.ts
```

Create files and subdirectories only when needed. A small feature may start with `index.ts` and a colocated test. A module may own multiple features; do not create a separate workspace package for every hook, component, or feature.

The existing `system` module owns `src/features/health/`. Future related system features belong beside `health`. Django modules remain under `libs/modules/`.

## Module boundaries

Applications import modules by package name, for example:

```ts
import { useHealthQuery } from '@outcometrik/system';
```

Export supported values and types explicitly from the module's `src/index.ts`. Keep implementation details private. Imports within a module use relative paths; consumers must not use paths such as `@outcometrik/system/src/features/health` or relative paths into another module.

Modules may use `@outcometrik/ui` and `@outcometrik/api`. Shared libraries must not import domain modules or applications. Keep dependencies acyclic. Where one module needs another, declare the workspace dependency and consume its public API. Compose workflows involving several modules in the application; extract a narrowly scoped shared contract only when there is a concrete need.

Domain-specific endpoint clients, query hooks, components, state, helpers, and tests belong to their feature. Share code between features inside the owning module before considering a repository-wide utility. Move code into shared libraries only when its responsibility and reuse justify it.

## React and state

Use function components and typed props. Keep components focused on presentation and interaction; put reusable domain workflows and data access behind feature hooks or functions. Keep state local unless multiple consumers need it. Derive values from authoritative state instead of synchronizing duplicate state with effects.

Use TanStack Query for server state, with keys that include the parameters affecting the response. Pass query cancellation signals through endpoint clients. Handle loading, error, empty, and success states explicitly. Root query providers and other application services belong in `apps/web/app/providers.tsx` or application setup.

Keep Next.js route files focused on route concerns and module composition. Add `'use client'` at the boundary that requires hooks, browser APIs, or event handlers; do not mark every library file as a client component. Never expose server secrets through client modules.

Use shared UI primitives where appropriate. Preserve semantic HTML, accessible names, keyboard operation, focus behavior, and status announcements. Feature UI stays in the feature; application shell UI stays in the app.

## TypeScript and API contracts

Follow the existing strict TypeScript configuration. Prefer explicit domain types and narrow unknown input at boundaries; avoid `any` and unsupported type assertions. Use `import type` and `export type` for type-only interfaces where practical.

Use `@outcometrik/api` for transport, credentials, CSRF, cancellation, and normalized errors. Feature endpoint clients own response validation and endpoint-specific types. A TypeScript generic does not validate a server payload. Authorization, scoring, and publication rules remain authoritative on the server.

Use PascalCase for React component names and types, and camelCase for functions, hooks, and values. Prefix hooks with `use`. Use descriptive domain names. Follow neighboring file conventions and the repository's Prettier and ESLint configuration rather than introducing a competing style.

## Registering and checking modules

The workspace glob `libs/ui/modules/*` discovers domain packages. Each new module needs a private package manifest with a root export and declared dependencies, plus an Nx library configuration with lint, test, and typecheck targets. Use the `system` module as the initial configuration example.

Register public package aliases in the root TypeScript configuration and any app configuration that overrides `paths`. Declare workspace dependencies in consuming packages. Include source packages in Next.js `transpilePackages` where needed. Update `pnpm-lock.yaml` without unrelated dependency upgrades.

Colocate tests with the behavior they cover. Test domain outcomes, validation, error handling, and important interactions. When moving existing code, move its tests with it. Run the affected module's lint, tests, and typecheck, plus the consuming app's typecheck. Run the web production build when package resolution or React client/server boundaries change.

Example commands for the existing module:

```sh
pnpm nx run ui-system:lint
pnpm nx run ui-system:test
pnpm nx run ui-system:typecheck
pnpm nx run web:typecheck
pnpm nx build web
```

These are contribution rules; documentation alone does not enforce import boundaries automatically. Keep reviews aligned with them and update the guide, module README, and configuration together when changing the architecture.
