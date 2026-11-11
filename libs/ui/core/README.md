# Core UI

Shared shadcn/ui components based on Radix, generated with the official CLI and
customized in source. Import supported primitives from `@outcometrik/ui`.
`src/components` owns controls, forms, dialogs, sidebar, cards and tables;
`src/lib/utils.ts` owns the class utility; `src/hooks` contains shared UI hooks.
No domain modules are imported here.

Run the shadcn CLI from `apps/web`; the configured aliases point at this package.
Review generated files, make their internal imports relative, add explicit public
exports, and declare package dependencies here. The application supplies semantic
theme tokens and Tailwind source scanning in `apps/web/app/globals.css`.

The `ui-core` Nx project provides lint, test and typecheck targets.
