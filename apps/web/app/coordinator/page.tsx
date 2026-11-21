import Link from 'next/link';
import { CoordinatorDashboard } from '@outcometrik/access';
import { CoordinatorAcademicOverview } from '@outcometrik/academic';
import { CoordinatorShell } from './_components/coordinator-shell';
import { CoordinatorCohortReports } from './coordinator-cohort-reports';

const GOVERNANCE_LINKS = [
  {
    href: '/coordinator/analytics',
    title: 'Cohort analytics & trends',
    detail: 'PO1–PO11 distributions, coverage, trends, and CSV/PDF exports.',
  },
  {
    href: '/coordinator/approvals',
    title: 'Syllabus approvals & weights',
    detail: 'Review A×LO / LO×PO matrices, lock drafts, and edit 1–5 Course→PO weights.',
  },
  {
    href: '/coordinator/po-sets',
    title: 'PO1–PO11 set manager',
    detail: 'Inspect archived and active PO sets, author drafts, and activate versions.',
  },
  {
    href: '/coordinator/publications',
    title: 'Calculations & publications',
    detail: 'Verify readiness gates, run calculations, and seal immutable series.',
  },
] as const;

export default function CoordinatorPage() {
  return (
    <CoordinatorShell
      activePath="/coordinator"
      title="Coordinator dashboard"
      description="Program governance workspace for cohort attainment analytics, syllabus approvals, PO1–PO11 sets, and immutable publications."
    >
      <nav
        aria-label="Coordinator governance shortcuts"
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
      >
        {GOVERNANCE_LINKS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="group flex flex-col justify-between gap-1.5 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)] transition-colors duration-150 hover:border-[var(--accent-border)] hover:bg-[var(--accent-soft)]/45 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="text-sm font-semibold text-foreground group-hover:text-[var(--accent-primary)]">
              {item.title} →
            </span>
            <span className="text-xs text-muted-foreground">{item.detail}</span>
          </Link>
        ))}
      </nav>

      <CoordinatorAcademicOverview embedded>
        <CoordinatorCohortReports />
      </CoordinatorAcademicOverview>

      <CoordinatorDashboard embedded />
    </CoordinatorShell>
  );
}
