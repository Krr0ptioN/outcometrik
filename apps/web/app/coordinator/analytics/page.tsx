'use client';

import { Suspense, useCallback, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { CohortOverview, ExportPanel } from '@outcometrik/reports';
import type {
  CohortFilterValues,
  CohortOverviewTab,
  CohortSelection,
} from '@outcometrik/reports';
import { Skeleton } from '@outcometrik/ui';
import { CoordinatorShell } from '../_components/coordinator-shell';

function CoordinatorAnalyticsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const programId = searchParams.get('program') ?? '';
  const publicationId = searchParams.get('publication') ?? '';
  const termId = searchParams.get('term') ?? '';
  const courseId = searchParams.get('course') ?? '';
  const rawTab = searchParams.get('tab');
  const activeTab: CohortOverviewTab =
    rawTab === 'trends' ? 'trends' : 'overview';

  const [selection, setSelection] = useState<CohortSelection>({
    programId: programId || null,
    publicationId: publicationId || null,
  });

  const syncUrl = useCallback(
    (next: Partial<CohortFilterValues> & { tab?: CohortOverviewTab }) => {
      const params = new URLSearchParams(searchParams.toString());
      const entries: Array<[string, string | undefined]> = [
        ['program', next.programId],
        ['publication', next.publicationId],
        ['term', next.termId],
        ['course', next.courseId],
        ['tab', next.tab],
      ];
      for (const [key, value] of entries) {
        if (value === undefined) continue;
        if (value === '' || (key === 'tab' && value === 'overview')) {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  const handleFiltersChange = useCallback(
    (filters: CohortFilterValues) => {
      syncUrl(filters);
    },
    [syncUrl],
  );

  const handleTabChange = useCallback(
    (tab: CohortOverviewTab) => {
      syncUrl({ tab });
    },
    [syncUrl],
  );

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
      <CohortOverview
        programId={programId}
        publicationId={publicationId}
        termId={termId}
        courseId={courseId}
        activeTab={activeTab}
        onFiltersChange={handleFiltersChange}
        onTabChange={handleTabChange}
        onSelectionChange={handleSelectionChange}
      />
      <ExportPanel
        scope="cohort"
        programId={selection.programId}
        publicationId={selection.publicationId}
        title="Scoped cohort export (CSV & PDF)"
      />
    </div>
  );
}

export default function CoordinatorAnalyticsPage() {
  return (
    <CoordinatorShell
      activePath="/coordinator/analytics"
      title="Cohort analytics & trends"
      description="Inspect immutable PO1–PO11 distributions, measurement coverage, exclusion breakdowns, chronological trends, and accreditation exports."
    >
      <Suspense
        fallback={
          <div className="space-y-4" role="status">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-72 w-full" />
          </div>
        }
      >
        <CoordinatorAnalyticsContent />
      </Suspense>
    </CoordinatorShell>
  );
}
