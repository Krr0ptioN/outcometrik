# ACAD-01 — Academic programs, courses, offerings, terms, and enrollments

**Blocked by:** BOOT-01.

## User story

As a coordinator, I can define a program's academic structure and offering roster, so a course run has an unambiguous term, section, program, staff, and eligible students.

## Rules

- Model institution, department, program, academic term, course, program-course association, course offering, instructor assignment, enrollment, and program membership.
- A course catalog identity is separate from its term-specific offering.
- An MVP offering belongs to exactly one target program and one PO-set version through its syllabus.
- Offering uniqueness is program + course + term + section; enrollment is unique per offering/student.
- A course may be owned by another department but must have an approved program-course association before contributing to a program.
- Enrollment status and attempt number are explicit; withdrawn/incomplete eligibility is policy-driven and recorded.
- Historical offerings, enrollments, and course associations are archived or protected, never silently deleted.
- New eligible offerings/enrollments increment the program/offering input revision used by calculations.

## Acceptance criteria

- [ ] Authorized users can create and browse the academic structure with scoped filtering.
- [ ] Duplicate terms, offerings, program-course links, memberships, and enrollments are rejected.
- [ ] An offering cannot be created for an inactive or unrelated program-course association.
- [ ] Roster status and attempt data are available to downstream calculations.
- [ ] Historical references remain readable after catalog edits.
