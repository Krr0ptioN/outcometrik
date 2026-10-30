# Outcometrik — Product Requirements Document

**Version:** 2.0 (DRAFT)
**Date:** 2026-10-30
**Status:** Product requirements; implementation details live elsewhere (ADRs, architecture doc)
**Project Members:** Mardin Nasout, Emir Şahin, Arsha Sharify Fakher, Mustafa Esad Yurt
**Supersedes:** `docs/PRD.md` (v1, planned to be replaced)

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
- **Instructor:** Edits syllabi, enters grades, views results for *assigned* offerings.
- **Student:** Views own published PO profile and grade evidence.

By default, access is denied unless explicitly granted. A user can hold multiple overlapping assignments (e.g., Instructor for CSE 311 *and* Student for CSE 321).

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

| Situation | Behaviour |
|---|---|
| Explicit grade of 0 | A real measured value, never treated as missing |
| Required grade absent | Blocks publication of the affected LO/PO |
| Excused/exempt assessment | Removed from the denominator, marked EXEMPT |
| No positive incoming weight | Null result (UNMAPPED / NOT_ASSESSED), never a numerical 0 |
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

TODO

## 12. Open decisions

Recorded as ADRs once resolved; the product is designed so each answer can change without rewriting historical results.

| Question | Default proposal |
|---|---|
| Who assigns the 1–5 course→PO weights, and per catalogue or per offering? | Coordinator, per offering, coordinator-editable |
| Retakes: latest approved attempt or all attempts? | Latest approved attempt only |
| Are provisional (in-progress) results visible to students? | Distinctly marked, or blocked pending publication policy |
| Is one-decimal ROUND_HALF_UP the official output convention? | Yes, pending confirmation |
| Grade excusals and withdrawals: block or renormalize? | Exempt removes weight from denominator |
