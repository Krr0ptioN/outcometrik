# Outcometrik — One-Pager

**Version:** 0.1 (DRAFT)
**Date:** 2026-10-15
**Owner:** [TBD]
**Change policy:** Edits require full team approval.

---

## Pitch

A web platform that computes each student's Program Outcome (PO) attainment from course grades, through weighted assessment-to-LO and LO-to-PO mappings, and presents traceable results to students, instructors, and coordinators.

## Problem

Instructors track outcome attainment in spreadsheets: grades live in one sheet, mappings in another, and weighted-average PO scores are recomputed by hand. Results are unauditable, error-prone, and invisible to students and the program.

## Users and capabilities

- **Program coordinator** defines the program's 11 outcomes, activates them, manages courses and offerings, and views cohort-level results.
- **Instructor** configures a course offering's outcomes, assessments, and mapping weights; enters grades; reviews computed results for their own offering.
- **Student** views their own PO profile and can trace any score back to the underlying grades and weights.
- Everyone sees only what their role and assignment authorize.

## Success criteria

- The verified reference scenario (two grades → two LOs → two POs) is reproduced exactly, including the documented edge cases (missing, zero, exempt, unmapped).
- Every published score is reproducible from stored inputs.
- A coordinator exports a cohort report; a student explains any score they see.
- Final demo, presentations, and both course reports delivered on schedule.

## Non-goals (this semester)

Video conferencing, learning-material hosting, chat, official transcripts or GPA, SIS/LMS replacement, plagiarism detection, multi-university tenancy. If a feature is not needed for the above capabilities, it is not built.

## Constraints

- Stack: Python + Django (fixed). Other technology choices are team decisions, recorded as ADRs.
- Team: exactly 4 members; single shared repository for both courses.
- Timeline anchors: presentations Nov 12 / Nov 17; final demo and printed reports Dec 29–30. Midterm weeks reduce capacity.

## Top risks / open questions

- Who assigns per-course 1–5 contribution weights? (→ ADR)
- Retake policy for cumulative scores. (→ ADR)
- Whether students may see provisional (in-progress) results. (→ ADR)

## Definition of MVP

Two configured course offerings whose grades flow through mappings into published, correct, traceable student PO profiles — nothing more until that loop works end-to-end.
