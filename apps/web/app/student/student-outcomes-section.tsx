'use client';

import { ExportPanel, StudentPOProfile } from '@outcometrik/reports';

export function StudentOutcomesSection() {
  return (
    <StudentPOProfile
      renderActions={(publicationId) => (
        <ExportPanel scope="student" publicationId={publicationId} />
      )}
    />
  );
}
