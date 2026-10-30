# Frontend domain modules

Each module is a workspace library at `libs/ui/modules/<module>/`, published internally as `@outcometrik/<module>`.

```text
<module>/
  src/
    index.ts
    features/
      <feature>/
        index.ts
        components/
        hooks/
  package.json
  project.json
  tsconfig.json
```

A module encapsulates multiple related features. Keep feature-specific API clients, state, hooks, UI, and tests together; create subdirectories only when needed. Export the supported module interface from `src/index.ts`. Consumers import the package name rather than feature internals. Compose cross-module workflows in the application and avoid circular module dependencies.

Modules may depend on shared UI (`libs/ui/core`) and transport (`libs/ui/api`). Shared libraries must not depend on domain modules. Next.js routes and application providers remain in `apps/web`.

The `system` module currently owns the health feature. Add further system features under its `src/features/` directory as they are implemented.

See the [canonical code style guide](../../../docs/CODE_STYLE.md) for dependency, React, API, and validation rules.
