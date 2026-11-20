import { CoordinatorDashboard } from '@outcometrik/access';
import { CoordinatorAcademicOverview } from '@outcometrik/academic';
import { CoordinatorCohortReports } from './coordinator-cohort-reports';

export default function CoordinatorPage() {
  return (
    <>
      <CoordinatorAcademicOverview>
        <CoordinatorCohortReports />
      </CoordinatorAcademicOverview>
      <CoordinatorDashboard />
    </>
  );
}
