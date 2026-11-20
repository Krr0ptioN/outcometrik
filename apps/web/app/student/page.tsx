import { StudentDashboard } from '@outcometrik/academic';
import { StudentOutcomesSection } from './student-outcomes-section';

export default function StudentPage() {
  return (
    <StudentDashboard>
      <StudentOutcomesSection />
    </StudentDashboard>
  );
}
