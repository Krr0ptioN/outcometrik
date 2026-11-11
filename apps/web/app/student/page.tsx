import { StudentDashboard } from '@outcometrik/academic';
import { ExportPanel } from '@outcometrik/reports';

export default function StudentPage() {
  return (
    <StudentDashboard>
      {/* publicationId stays null until the publication API exists (see EXP-01 contract). */}
      <ExportPanel scope="student" publicationId={null} />
    </StudentDashboard>
  );
}
