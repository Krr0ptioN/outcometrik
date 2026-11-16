# Academic UI

`@outcometrik/academic` owns coordinator, instructor, and student academic workspaces.
It uses the public session contract from `@outcometrik/access`, shared transport,
and shared UI components.

The current instructor dashboard shows assigned offerings and authorized roster
status. The student dashboard shows the signed-in student's own enrollments. The
coordinator dashboard shows memberships and offering counts inside managed
programs. Grade entry and published outcome profiles require the gradebook and
publication domain models before those workflows can be completed.

Instructors can manage versioned syllabi for assigned offerings, including draft
learning outcomes and assessments, and revisions of approved versions. Program
coordinators can register and activate program outcome sets and approve syllabi
for their managed offerings. Drafts can be bound to the current active outcome
set before approval; server authorization and validation remain authoritative.
