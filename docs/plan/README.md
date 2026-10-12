# Outcometrik implementation tickets

These tickets are derived from [`docs/PRD.md`](../PRD.md). Each story is a vertical slice with its own rules and acceptance criteria. A ticket may start when every ticket listed under **Blocked by** is complete.

Dependency order:

`BOOT-01` → `BOOT-02`, `AUTH-01`, `ACAD-01` → `OUT-01`, `CUR-01` → `CUR-02` → `CUR-03` → `CALC-02` → `CALC-03` → `ANA-01` → `EXP-01`

`CALC-01` can start independently and joins `CALC-02`. `GRD-01` depends on `CUR-01` and `AUTH-01`; `IMP-01` depends on `GRD-01`; `UI-01`, `UI-02`, and `UI-03` also require `BOOT-02` and their domain slice. `OPS-01` starts after `BOOT-01`. `PERF-01` depends on `ANA-01`. `e2e` validation is represented by the acceptance criteria across the slices.

The PRD marks several policies as proposed. Implement them behind a policy/version boundary and record the selected policy in the ticket's tests; do not silently turn a proposal into an institutional rule.
