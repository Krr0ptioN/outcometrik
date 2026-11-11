# Academic UI

`@outcometrik/academic` owns coordinator, instructor, and student academic workspaces.
It uses the public session contract from `@outcometrik/access`, shared transport,
and shared UI components.

The instructor dashboard shows assigned offerings and authorized roster status. The
gradebook at `/instructor/gradebook` selects approved assessments, creates batches,
records scored/zero/missing/exempt/withdrawn/incomplete results, corrects existing
grades with optimistic versions, shows append-only history, and releases batches to
students. The student dashboard lists only grades returned by the released-grade API.
Assessment authoring is not part of GRD-01; the gradebook reads approved assessments
from the scoped API and displays an empty state when curriculum setup is incomplete.
The coordinator dashboard shows memberships and offering counts inside managed
programs. Published outcome profiles remain a downstream workflow.

The gradebook consumes `GET /api/v1/assessments/?offering={id}`, grade-batch list/create/release,
and grade list/create/correct/history endpoints. Approved assessments are visible only to staff
with `grades.edit` on the offering. Student grade lists expose only released records for the
signed-in student.
