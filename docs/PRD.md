# Outcometrik — Product Requirements Document

**Version:** 2.0 (DRAFT)
**Date:** 2026-10-30
**Status:** Product requirements; implementation details live elsewhere (ADRs, architecture doc)
**Project Members:** Mardin Nasout, Emir Şahin, Arsha Sharify Fakher, Mustafa Esad Yurt
**Authority:** Main product requirements document. Supersedes v1; unresolved policies remain proposals.
**Supporting material:** [Historical v1 design and delivery reference](reference/v1-design-and-delivery.md). This reference does not add product scope or override this document.

---

## 1. Pitch

A web platform that computes each student's Program Outcome (PO) attainment from course grades and Learning Outcome (LO) attainment through weighted assessment-to-LO and LO-to-PO mappings, and presents traceable, explainable results to students, instructors, and coordinators.

Pilot customer: Acıbadem University Computer Engineering, which defines eleven program outcomes (PO1–PO11).

## 2. Problem

Instructors track outcome attainment in spreadsheets: grades live in one sheet, mappings in another, and weighted-average PO scores are recomputed by hand. Results are unauditable, error-prone, and invisible to students and the program.

## 3. Roles and capabilities

Access is built on two layers:

- **Roles** (standard sets of permissions): Administrator, Program Coordinator, Instructor, Student.
- **Capabilities** (individual actions like "View Cohort", "Edit Grades", "Approve Syllabus").

A Role grants a bundle of Capabilities, but individual Capabilities can be granted directly to a user for specific situations without changing their Role.

- **Administrator:** Full system access; manages users, settings, and delegates roles.
- **Program Coordinator:** Manages course/PO catalogs, assigns instructors, approves mappings, publishes results, views analytics.
- **Instructor:** Edits syllabi, enters grades, views results for _assigned_ offerings.
- **Student:** Views own published PO profile and grade evidence.

By default, access is denied unless explicitly granted. A user can hold multiple overlapping assignments (e.g., Instructor for CSE 311 _and_ Student for CSE 321).

## 4. How scoring works

Every published score must be reproducible from stored inputs: grades, mappings, and weights. All arithmetic uses decimal types — never binary floats. This is for grade calculation accuracy. Scores are kept at full precision internally and rounded to one decimal place (`ROUND_HALF_UP` proposed) only at display and export.

### 4.1 Normalization

Raw grades are points earned out of points possible, normalized to a 0–100 scale:

```
score100 = 100 × points_earned / points_possible
```

> [!TIP]
> For example: Results of an exam that's graded out of 20 points will be expanded to a 100-point scale by multiplying the earned score by 5.

### 4.2 Universal aggregation rule

In score calculations of outcomes, each score is calculated using the aggregate input scores and weights using this formula:

```
score = Σ (weight × source_score) / Σ (weight)
```

> [!NOTE]
> **Weights are relative importance values, not percentages.** They do not need to sum to 100 — a weight of 40 is simply twice as influential as a weight of 20. Only sources with a weight greater than zero participate.

### 4.3 The three levels

1. **Grades → Learning Outcomes** (within a course offering). How assessments feed LOs is an implementation choice; Outcometrik uses relative per-assessment weights (e.g. Midterm 60, Project 40), entered by the instructor in a matrix editor.
2. **Learning Outcomes → Program Outcomes** (within a course offering). Each LO→PO link carries an **integer weight from 1 to 5**, set per course and PO pair, expressing how strongly the course's outcomes contribute to that program outcome.
3. **Courses → Student PO** (across offerings). Each course that contributes to a PO also carries a 1–5 relevance weight; a student's cumulative PO combines every contributing course with the same weighted-average rule.

### 4.4 States and edge cases

| Situation                       | Behaviour                                                  |
| ------------------------------- | ---------------------------------------------------------- |
| Explicit grade of 0             | A real measured value, never treated as missing            |
| Required grade absent           | Blocks publication of the affected LO/PO                   |
| Excused/exempt assessment       | Removed from the denominator, marked EXEMPT                |
| No positive incoming weight     | Null result (UNMAPPED / NOT_ASSESSED), never a numerical 0 |
| Input changed after publication | Historical snapshot unchanged; current state flagged STALE |

A published score is an immutable snapshot; correcting a grade afterwards requires a new calculation run and a fresh publication.

## 5. Verified reference scenario

The scoring engine must reproduce this scenario exactly (Midterm = 90, Project = 80):

```
LO1 = (90×60 + 80×40) / (60 + 40)              = 86.0
LO2 = (90×40 + 80×100) / (40 + 100)            = 82.857… → displays 82.9

PO1 = (86.0×2 + 82.857…×1) / (2 + 1)           = 84.952… → displays 85.0
PO2 = 82.857…                                    → displays 82.9
```

Intermediate values are never rounded before further aggregation (PO1 above uses 82.857…, not 82.9). These four values — 86.0, 82.9, 85.0, 82.9 — are the acceptance test for the calculation core.

## 6. Product surface

The UI is a thin, role-scoped web application wedged over the calculation engine. Four surfaces matter:

1. **Mapping Studio** (instructor): two spreadsheet-like matrices — assessments × LOs and LOs × POs — with inline validation (orphan LOs, unreachable POs, invalid weights). Mappings live in a syllabus version; after coordinator approval, changes require a new revision, never an in-place rewrite.
2. **Gradebook** (instructor): roster × assessment grid with explicit zero/absent/exempt states, and CSV bulk import with dry-run validation.
3. **Outcome Profile** (student): all eleven POs as scored bars, with drill-down from any PO through courses and LOs down to the raw grades, weights, and formula that produced it.
4. **Cohort Overview** (coordinator): program-level averages, distributions, and measurement coverage per PO, with export.

Presentation rules: missing data renders as an em dash or "not assessed", never as a zero-height bar; provisional results are visually distinct from published ones; every chart states its sample size and coverage.

## 7. Integrations

CSV is the primary integration format for grade ingestion, rosters, and report export — with a dry-run/preview step before any write. PDF export serves student and cohort reports. Potential third-party integrations are optional; nothing in the core depends on them.

## 8. Constraints

- **Stack:** Python + Django (mandated, no exceptions). All other technology choices are team decisions recorded as ADRs.
- **Team:** exactly 4 members, one shared repository, same team for both courses.
- **Language:** English for documentation and code.
- **Timeline:** presentations Nov 12 (CSE 321) / Nov 17 (CSE 311); final demo and printed reports Dec 29–30. Midterm weeks (Nov 10–13, Nov 19–24, Dec 22–24) reduce capacity.

## 9. Non-goals

Official transcripts/GPA, Plagiarism detection, video conferencing, chat, learning-material hosting, multi-university tenancy, automatic unapproved syllabus configuration. Basic functionality meets only average expectations; anything built beyond this PRD must be genuinely useful to its users.

## 10. Success criteria

- The verified reference scenario reproduces exactly, including all documented edge cases.
- Every published score is reproducible from stored, versioned inputs.
- Two configured course offerings feed a cumulative student PO profile through 1–5 course weights.
- A coordinator exports a cohort report; a student can explain any score they see.
- No user can read data outside their role and scope.
- Final demo, presentations, and both course reports delivered on schedule.

## 11. MVP requirements

The requirements below make the scope in §§1–10 testable. Existing FR identifiers are retained where applicable; v2 takes precedence over older tickets and design documents. Technical choices belong in architecture documents and ADRs. Optional or stretch items from v1 are not MVP commitments.

### 11.1 Identity, capabilities and academic setup

- **AUTH-01:** Authenticate users and enforce scoped role bundles and direct capability grants on every protected action. Direct grants do not imply access outside their assigned scope. Support overlapping assignments; deny actions with no applicable grant.
- **FR-101–105:** Administrators and authorized coordinators configure the pilot program, its eleven ordered POs, course catalog, terms, offerings, instructor assignments and student rosters. Support manual enrollment and CSV preview/import with duplicate detection.
- Store authoritative PO descriptions with source and effective version. Activating a revised PO set preserves the version used by historical syllabi and publications.
- Distinguish a catalog course from an offering in a term/section and bind each pilot offering to its target program and PO set. Course ownership must not accidentally grant access to another program's students.

**Acceptance:** An active pilot program exposes PO1–PO11; duplicate enrollment is rejected. An instructor can edit an assigned offering but cannot edit an unrelated offering by changing a URL or identifier. A scoped direct capability enables only its granted action and scope; removing it removes that access unless another applicable assignment grants it. Students cannot retrieve another student's records or exports.

### 11.2 Syllabi and Mapping Studio

- **FR-201–202:** Instructors create draft LOs and assessments for assigned offerings. Each assessment has positive points possible. Assessment→LO weights are nonnegative relative values; their sum is not constrained to 100.
- **FR-203:** Each active LO→PO link has an integer weight from 1–5. An absent link contributes nothing. Do not retain v1's 0–100 LO→PO input range.
- **FR-204:** Record an independent integer 1–5 relevance weight for each contributing course/PO pair. Authority and catalog-versus-offering ownership remain open under §12.
- **FR-205:** Validate both matrices for invalid weights, orphan LOs, unreachable POs and incompatible syllabus/PO versions. Sparse mappings are supported; displaying eleven POs does not require every course to measure all eleven.
- **FR-206–207:** Coordinators approve syllabus versions. Approved LOs, assessments and mappings are immutable; subsequent edits create a revision, preserving historical evidence.

**Acceptance:** The matrices accept assessment weights 60/40 and 40/100, and LO→PO weights 2/1 for PO1 and 1 for PO2. Fractional or out-of-range LO→PO and course→PO weights are rejected. Approval locks the version; a later revision does not rewrite a published score's inputs.

### 11.3 Gradebook and CSV workflows

- **FR-301–302:** Show roster × assessment grades, distinguish numeric zero, absent and authorized exempt states, and validate earned points against the assessment's positive maximum.
- **FR-303–304:** Provide CSV templates, dry-run preview, row-specific errors and explicit confirmation before writing grades or roster changes. Apply validated imports atomically; repeating the same import must not duplicate records. Reject stale previews when their underlying configuration or data has changed.
- **FR-305–306:** Record who changed a grade, when, and why for post-publication corrections. Prevent silent concurrent overwrites and control student visibility through the release/publication policy.

**Acceptance:** A 100-row synthetic grade import can be previewed and applied. An invalid row yields an actionable error and no partial application. Zero remains a measured score; an absent required grade is never converted to zero. An authorized correction preserves the earlier publication and its evidence.

### 11.4 Calculation, evidence and publication

- **FR-401–402:** Normalize points and apply the three weighted means in §4 using decimal arithmetic without intermediate display rounding. Cumulative scores use course relevance, not automatically course credits or ECTS.
- **FR-403:** Preserve the states in §4.4. Resolve missing required inputs, exemptions and eligible course attempts before publication. A missing denominator produces a null result and a reason.
- **FR-404:** Retain enough evidence to reproduce each result: raw points and maximum, normalization, participating inputs and weights, numerator, denominator, intermediate results, syllabus/PO versions and calculation policy.
- **FR-405–406:** Identify each calculation run and its input versions; an authorized coordinator publishes an immutable snapshot with approver and timestamp. Recheck input freshness at publication. Changed inputs require a new run and publication; historical values remain readable with a derived freshness indicator.
- Apply the agreed eligibility and retake policy consistently and retain its version. Do not silently finalize the proposals in §12 or combine incompatible PO definitions into one cumulative score.

**Acceptance:** §5 produces 86.0, 82.9, 85.0 and 82.9 on display. Independently supplied course scores 85 and 90 with relevance weights 5 and 3 produce 86.875, displayed as 86.9 under the proposed rounding convention. Required missing grades block affected publication; authorized exemptions remove their weight. Repeating a run with identical inputs and policy reproduces its results. Editing a grade after calculation cannot publish a stale run as current.

### 11.5 Student, instructor and coordinator surfaces

- **FR-501–504:** Students see their own published eleven-PO profile and reports, including null indicators. Drill-down follows PO → courses → LOs → assessments to original grades, weights and formulas. Identify the term and publication version; retain access to authorized historical snapshots.
- **FR-601–602:** Instructors navigate assigned offerings, see configuration readiness, edit permitted drafts and use the gradebook/import workflow. Faculty previews must clearly identify incomplete or provisional results.
- **FR-701, FR-703–705:** Coordinators see cohort averages, distributions and measurement coverage per PO, unmapped outcomes, publication state and stale warnings. Include sample size, population definition and PO-set version. Exclude unmeasured values from numeric averages while reporting missing coverage.
- Export scoped student and cohort reports in CSV and PDF, preserving displayed values, coverage, publication identity and explanation context. Export access follows the same rules as on-screen access.

**Acceptance:** A student can explain every displayed numerical score from its evidence. A cohort with one measured zero and one unmeasured student reports zero for the measured population, n=1 and explicit missing coverage. Unmeasured outcomes do not appear as zero-height bars. Reports match their selected publication and cannot expose other scopes.

### 11.6 Quality and delivery acceptance

- Preserve audit history for sensitive configuration, permission, grade and publication changes and authorized exports. Keep student data private in logs and reports; use synthetic demo data unless real data is explicitly authorized.
- Validate imports and protect spreadsheet exports from formula execution. Preserve existing publications during failed writes or recalculation; demonstrate backup recovery before real pilot use.
- Make matrices, grade entry and navigation keyboard-operable with accessible labels, focus and errors. Provide textual values alongside charts and distinguish provisional, missing and published states without relying solely on color.
- Demonstrate two configured offerings contributing to a cumulative profile, all eleven POs, missing and exempt cases, correction followed by republication, and a coordinator export. The development setup and demonstration data must be reproducible.
- Deliver authentic course reports: CSE311 covers backlog, work/velocity, Git activity, branching, CI/CD and applied Getting Real principles; CSE321 covers introduction, system design, measured data model, scalability/fault tolerance, consistency and teamwork. Preserve the assignment's formatting: no separate cover page, team/members/repository on the first page, readable figures and printed final copies.

**Acceptance:** Scoring, authorization, import rollback, version conflicts and immutable publication scenarios pass automated checks. A keyboard walkthrough completes the core workflows. Both course reports describe actual implementation and measurements. V1 performance numbers and infrastructure proposals remain planning references, not newly mandated product scope.

### 11.7 Scope reconciliation

V2 retains the v1 core of academic setup, versioned curricula, grading, three-stage scoring, evidence, publication and scoped reporting. V2 explicitly includes PDF/CSV reporting and direct capability grants. Its 1–5 LO→PO links replace v1's relative 0–100 links; v1's 100:50 example is represented as 2:1 without changing the calculation.

V1's optional syllabus extraction, rubric scoring, what-if previews, longitudinal comparison, notifications, scheduled jobs and SIS/LMS connectors are not added to this MVP. Optional TA/reviewer roles are not additional required roles; delegated access follows v2's capability model. Technical schemas, stack proposals, backlog estimates and historic delivery plans are retained in the supporting reference, subject to this PRD and later ADRs.

## 12. Open decisions

Recorded as ADRs once resolved; the product is designed so each answer can change without rewriting historical results.

| Question                                                                  | Default proposal                                         |
| ------------------------------------------------------------------------- | -------------------------------------------------------- |
| Who assigns the 1–5 course→PO weights, and per catalogue or per offering? | Coordinator, per offering, coordinator-editable          |
| Retakes: latest approved attempt or all attempts?                         | Latest approved attempt only                             |
| Are provisional (in-progress) results visible to students?                | Distinctly marked, or blocked pending publication policy |
| Is one-decimal ROUND_HALF_UP the official output convention?              | Yes, pending confirmation                                |
| Grade excusals and withdrawals: block or renormalize?                     | Exempt removes weight from denominator                   |
