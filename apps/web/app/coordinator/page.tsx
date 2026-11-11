import { CoordinatorDashboard } from '@outcometrik/access';
import { CoordinatorAcademicOverview } from '@outcometrik/academic';
export default function CoordinatorPage() {
  return (
    <>
      <CoordinatorAcademicOverview />
      <CoordinatorDashboard />
    </>
  );
}
