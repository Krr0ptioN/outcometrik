import { CoordinatorDashboard } from '@outcometrik/access';
import { CoordinatorAcademicOverview } from '@outcometrik/academic';
import { ExportPanel } from '@outcometrik/reports';
export default function CoordinatorPage() {
  return (
    <>
      <CoordinatorAcademicOverview>
        {/* publicationId and programId come from the publication API once it exists. */}
        <ExportPanel
          scope="cohort"
          publicationId={null}
          title="Cohort report"
        />
      </CoordinatorAcademicOverview>
      <CoordinatorDashboard />
    </>
  );
}
