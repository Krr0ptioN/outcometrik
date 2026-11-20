import { CoordinatorPOSetManager } from '@outcometrik/academic';
import { CoordinatorShell } from '../_components/coordinator-shell';

export default function CoordinatorPOSetsPage() {
  return (
    <CoordinatorShell
      activePath="/coordinator/po-sets"
      title="Versioned PO1–PO11 set manager"
      description="Inspect historical and active Program Outcome sets, author new draft revisions, and activate immutable PO sets for accreditation."
    >
      <CoordinatorPOSetManager />
    </CoordinatorShell>
  );
}
