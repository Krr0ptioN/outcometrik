'use client';

import { useCallback, useState } from 'react';
import { CohortOverview, ExportPanel } from '@outcometrik/reports';
import type { CohortSelection } from '@outcometrik/reports';

export function CoordinatorCohortReports() {
  const [selection, setSelection] = useState<CohortSelection>({
    programId: null,
    publicationId: null,
  });

  const handleSelectionChange = useCallback((next: CohortSelection) => {
    setSelection((prev) =>
      prev.programId === next.programId &&
      prev.publicationId === next.publicationId
        ? prev
        : next,
    );
  }, []);

  return (
    <div className="space-y-6">
      <CohortOverview onSelectionChange={handleSelectionChange} />
      <ExportPanel
        scope="cohort"
        programId={selection.programId}
        publicationId={selection.publicationId}
        title="Cohort report"
      />
    </div>
  );
}
