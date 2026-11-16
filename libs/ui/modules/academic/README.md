# Academic UI

`@outcometrik/academic` owns coordinator, instructor, and student academic workspaces.
It uses the public session contract from `@outcometrik/access`, shared transport,
and shared UI components.

Institution administrators can create departments, programs, terms, courses,
program-course links, offerings, program memberships, instructor assignments,
and enrollments at `/admin/academic`. The screen calls the scoped academic API;
the API remains authoritative for permissions, relationships, and roster rules.
Create an approved program-course link before creating its offering. Create and
activate student accounts in People & access before adding memberships and
enrollments.

The current instructor dashboard shows assigned offerings and authorized roster
status. The student dashboard shows the signed-in student's own enrollments. The
coordinator dashboard shows memberships and offering counts inside managed
programs. Grade entry and published outcome profiles require the gradebook and

publication domain models before those workflows can be completed. Those
downstream endpoints must use AUTH-01's shared scoped selectors and service checks.

Instructors can manage versioned syllabi for assigned offerings, including draft
learning outcomes and assessments, and revisions of approved versions. Program
coordinators can register and activate program outcome sets and approve syllabi
for their managed offerings. Drafts can be bound to the current active outcome
set before approval; server authorization and validation remain authoritative.
