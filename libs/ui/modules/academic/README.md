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

The instructor dashboard at `/instructor` uses a workspace sidebar with overview and
grades/roster operations. It shows assigned offerings and active roster counts; each
offering opens its gradebook directly. The gradebook at `/instructor/gradebook` remains
available as a standalone route. It selects approved assessments, creates and releases
batches, and records scored/zero/missing/exempt/withdrawn/incomplete results. Instructors
can search the roster, filter students by grade status, see completion counts, correct
grades with optimistic versions, and inspect append-only history. Released-grade entry
and corrections prompt for a reason; inactive enrollments remain visible but cannot be
graded. Loading, empty, save, validation, and conflict states are announced in the
interface. The student dashboard lists only grades returned by the released-grade API.
Assessment authoring is not part of GRD-01; the gradebook reads approved assessments
from the scoped API and displays an empty state when curriculum setup is incomplete.
The coordinator dashboard shows memberships and offering counts inside managed
programs. Published outcome profiles remain a downstream workflow.

The gradebook consumes `GET /api/v1/assessments/?offering={id}`, grade-batch list/create/release,
and grade list/create/correct/history endpoints. Approved assessments are visible only to staff
with `grades.edit` on the offering. Student grade lists expose only released records for the
signed-in student.

For request and authorization details, see the [gradebook API contract](../../../../apps/api/README.md#gradebook-api-grd-01).
The assessment model is currently a CUR-01 stub. Versioned syllabus integration and
publication staleness remain downstream work; the UI does not implement them.

