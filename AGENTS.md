# Repository instructions

@/home/master/.codex/RTK.md

When a live Hunk session is available, activate the `hunk-review` skill and use `hunk session *` commands to inspect, navigate, reload, and annotate the review. Do not launch Hunk's interactive TUI from Codex.

## Code style and architecture

Read and follow [the code style guide](docs/CODE_STYLE.md) before changing application or library code. It is the canonical source for frontend module conventions; update it when an agreed convention changes.

- Put frontend domain modules in `libs/ui/modules/<module>/`, with related features inside `src/features/<feature>/`.
- Each module is a workspace package named `@outcometrik/<module>` and an Nx library named `ui-<module>`.
- Import another module through its explicit public exports in `src/index.ts`. Do not deep-import its features or source files.
- Keep feature-specific components, hooks, endpoint clients, types, state, and tests within the owning feature. Do not put domain features in `apps/web/lib` or shared UI packages.
- Keep routes, application bootstrap, and root providers in `apps/web`. Compose workflows spanning modules there.
- Shared UI and transport libraries must not depend on domain modules. Keep module dependencies acyclic; use public APIs for necessary dependencies.
- Follow existing TypeScript, React, API, accessibility, and validation conventions described in the guide. Preserve unrelated work.
- For a new module, register its workspace package, Nx targets, dependencies, TypeScript paths, and Next.js transpilation where needed. Update the lockfile and relevant documentation.
- Run affected tests, lint, and type checks; run the web build when changing module resolution or client/server boundaries. Report any checks blocked by the environment.
