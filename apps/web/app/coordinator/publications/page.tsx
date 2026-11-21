import { CoordinatorPublicationsManager } from '@outcometrik/academic';
import { CoordinatorShell } from '../_components/coordinator-shell';

export default function CoordinatorPublicationsPage() {
  return (
    <CoordinatorShell
      activePath="/coordinator/publications"
      title="Calculation runs & immutable publications"
      description="Verify pre-publication readiness gates, run deterministic decimal calculations, and seal immutable publication series with manifest hashes."
    >
      <CoordinatorPublicationsManager />
    </CoordinatorShell>
  );
}
