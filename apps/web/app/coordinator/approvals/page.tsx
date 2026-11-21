import { CoordinatorApprovalsPanel } from '@outcometrik/academic';
import { CoordinatorShell } from '../_components/coordinator-shell';

export default function CoordinatorApprovalsPage() {
  return (
    <CoordinatorShell
      activePath="/coordinator/approvals"
      title="Syllabus approvals & Course→PO weights"
      description="Review draft A×LO and LO×PO mapping matrices before locking syllabus versions, and maintain 1–5 Course→PO relevance weights across linked programs."
    >
      <CoordinatorApprovalsPanel />
    </CoordinatorShell>
  );
}
