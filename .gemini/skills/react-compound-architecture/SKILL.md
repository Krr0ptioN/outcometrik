---
name: react-compound-architecture
description: "SOLID + GoF Compound Component Architecture for complex and organism React components in Outcometrik. Load whenever building or refactoring multi-state, query-backed, or multi-section frontend organisms."
---

# React Compound Architecture (SOLID + GoF)

Use this skill whenever designing, building, or refactoring **complex or organism-level React components** (dashboards, analytics panels, approval queues, editable matrices, multi-dialog managers, and any view orchestrating TanStack Query states).

## 1. Core Architectural Rule: No Monolithic Organisms, No Prop Hell

An organism component must **never** combine:
- 4+ unrelated `useState` hooks + multiple `useMutation` / `useQuery` hooks + raw `isPending` / `isError` / `empty` JSX branching + multiple tables/charts/dialogs in a single file.
- Mega-wrapper components that force callers to unpack 6–10 configuration props (`isPending`, `isError`, `error`, `data`, `loading`, `empty`, `errorTitle`, `formatError`, etc.).

Instead, apply the **Adapter + Composite (Compound Components) + Factory Method** triad alongside **SOLID** decomposition.

## 2. Async State Handling: `QueryState` & `createQueryState`

`@outcometrik/ui` provides `QueryState` and `createQueryState` ([query-state.tsx](../../../libs/ui/core/src/components/query-state.tsx)):

- **Adapter**: Pass the TanStack `query` object directly (`query={analyticsQuery}`) instead of unpacking `isPending`, `isError`, `error`, and `data`.
- **Factory Method**: Bind each domain module's error formatter once via `createQueryState({ formatError })` so call sites never repeat `format={...}`.
- **Composite (Compound Components)**: Compose `Loading`, `Error`, `Empty`, and `Ready` as JSX children — omit any slot that uses defaults or is not needed.

### Canonical Usage

```tsx
import { createQueryState } from '@outcometrik/ui';
import { cohortErrorMessage } from '../api';

// 1. Bind once per feature/module (Factory Method)
const CohortQuery = createQueryState({ formatError: cohortErrorMessage });

// 2. Compose cleanly inside the organism (Adapter + Composite)
<CohortQuery
  query={analyticsQuery}
  isEmpty={(data) => data.outcomes.length === 0}
  treatErrorAsEmpty={(err) => err instanceof ApiError && err.status === 404}
>
  <CohortQuery.Loading label="Loading cohort analytics…" />
  <CohortQuery.Error title="Unable to load cohort analytics" />
  <CohortQuery.Empty>
    <NoAnalyticsEmptyState />
  </CohortQuery.Empty>
  <CohortQuery.Ready>
    {(analytics) => (
      <>
        <CohortTraceabilityHeader analytics={analytics} />
        <PoAttainmentBarChart outcomes={analytics.outcomes} />
        <CohortSummaryTable
          publicationId={analytics.publication_id}
          poSetVersion={analytics.po_set_version}
          outcomes={analytics.outcomes}
        />
      </>
    )}
  </CohortQuery.Ready>
</CohortQuery>
```

### Extending Slots (Open–Closed Principle)
- **Custom loading geometry**: Pass layout-matched skeletons as children of `<DomainQuery.Loading>`.
- **Custom error rendering**: Pass a render function `(error, message) => <CustomAlert />` to `<DomainQuery.Error>`.
- **Synchronous override**: Pass `fallbackData={providedItems}` when a component supports both controlled prop data and fetched data.

## 3. SOLID Decomposition Checklist for Organisms

Before shipping any organism component:

1. **Single Responsibility (SRP)**:
   - Keep the top-level organism as a thin composition orchestrator (~150–350 lines max).
   - Extract pure domain formatters, validators, and lookup mappers into a plain `.ts` module (no React imports).
   - Extract each independent interactive region (filter bar, chart, summary table, approval queue, editable matrix, dialogs) into its own file.
2. **State Isolation (`react-component-performance`)**:
   - Co-locate fast-changing local state (hover, draft cell edits, dialog open/form state, tab-local filters) inside the leaf/sub-organism that owns it so sibling tables and charts never re-render.
   - Use React `key={scopeId}` on sub-organisms to reset local state on scope switches instead of `useEffect` state synchronization.
3. **Avoid Prop Drilling — Feature Context & Custom Hooks**:
   - Never pass 5+ shared filter/scope/selection props down through intermediate containers. Expose a feature-scoped React Context + custom hook (e.g. `CohortOverviewProvider` + `useCohortOverviewContext()`) so child panels (`<CohortFilterBar />`, `<CohortTrendsPanel />`) read only what they need directly.
   - Extract repeated multi-query + derived-state orchestration (e.g. `useCoordinatorProgramScope()`) into reusable feature custom hooks instead of duplicating query chains across organisms.
   - Wrap pure presentational leaves in `React.memo` and stabilize callbacks with `useCallback` / functional `setState`.
4. **Conditional Rendering (`docs/CODE_STYLE.md`)**:
   - Use `{condition && <Component />}` for single-branch renders when `condition` is a boolean or non-numeric truthy guard.
   - Always guard numeric counts explicitly (`items.length > 0 && <List />`) so `0` is never rendered into the DOM.
   - Reserve `condition ? <A /> : <B />` for genuine two-branch renders.
