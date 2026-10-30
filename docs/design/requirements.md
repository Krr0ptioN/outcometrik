# Outcometrik — architecture requirements

Source: [PRD v1.0](../PRD.md), 9 October 2026. This is a proposed design, not an implementation or a statement of institutional policy.

## Core functional scope

1. Configure a program's eleven POs and approve versioned course syllabi, assessments and the three distinct mapping weights (FR-100/200).
2. Enter grades and atomically apply validated CSV imports with scoped permissions and correction history (FR-300).
3. Compute LO → course PO → student PO with deterministic arithmetic, completeness states and reproducible evidence; publish immutable snapshots (FR-400).
4. Serve students' own released profiles and faculty's scoped cohort reports, with version, sample size and coverage (FR-500/600/700).

## Non-functional requirements

| Dimension | Design target / assumption | Verification |
|---|---|---|
| Scale | 1,000 active students, 10 enrollments/student/year, 8 assessments/offering; 200 concurrent users | Synthetic dataset; no real student records |
| Traffic | 40 peak read requests/s; 10 peak write requests/s; 4:1 burst read/write ratio | Mixed workload with grade-release burst |
| Latency | Common scoped CRUD p95 <500 ms; 1,000 × 10-course scoring p95 <5 s | PRD §15; record hardware, queries and evidence volume |
| Availability | Restart recovery required; proposed 99.5% during agreed pilot hours, excluding scheduled maintenance | Synthetic checks; single-host deployment cannot guarantee HA |
| Consistency | Atomic imports, optimistic edit conflicts, fresh-input publication gate; immutable historical reads | PostgreSQL concurrency tests |
| Durability | Proposed RPO ≤24 h and RTO ≤4 h with daily encrypted off-host backups | Restore rehearsal; upgrade before real institutional use |
| Security | Deny by default; 0 accepted cross-student/cross-program disclosures | Positive and negative object-scope tests |
| Numeric behavior | Decimal precision 50, fixed operation order, display ROUND_HALF_UP to 0.1 | Canonical examples, boundary cases, replay tests |
| Accessibility | Keyboard-operable tables and chart data alternatives | Manual verification; no numeric compliance claim |

Targets are proposals, not measured results. RPO/RTO and retention require operator approval before real-data use.

## Explicit exclusions

Official transcripts/GPA, SIS/LMS synchronization, automated mapping approval, billing, microservices, multi-region HA and true cross-program offerings. Retake, release and excusal policies remain configurable proposals. PDF export is P1; CSV and evidence drill-down come first.

## Load-bearing assumptions

- One offering targets one program and one immutable approved syllabus/PO-set version; ownership of a service course may be elsewhere.
- Latest completed approved attempt per catalog course is the proposed cumulative policy. Profiles never combine semantically different PO-set versions without an explicit approved conversion policy.
- Faculty previews may be incomplete. Students receive only authorized released grades and published outcomes; unassessed is null, not zero.
- React is built separately and served at the same public origin as Django, enabling session cookies and CSRF protection.
- Initial calculations and bounded CSV operations run synchronously. Queue/worker deployment is conditional on benchmarks.
- A four-person semester team operates one modular monolith and one PostgreSQL primary.

## Numbers driving the design

At these assumptions: 80,000 grade facts/year; approximately 724,000 outcome rows/year and 2.12 million evidence edges/year at four retained runs. Estimated incremental logical storage is ~1.41 GB/year before database/index overhead, or ~4.2 GB/year at a provisional 3× allowance. Peak JSON egress is ~0.8 MB/s at 40 reads/s × 20 KB. See [system design](outcometrik.md#2-scale-and-capacity-hypothesis) for derivation and uncertainties.
