'use client';

import { Skeleton, createQueryState } from '@outcometrik/ui';
import { cohortErrorMessage } from '../api';
import type { CohortTrendsResponse } from '../types';
import { TrendsComparisonTable } from './trends/trends-comparison-table';
import { TrendsOutcomeChart } from './trends/trends-outcome-chart';
import { TrendsSnapshotPicker } from './trends/trends-snapshot-picker';
import { TrendsStoreProvider } from './trends/trends-store-context';
import { useTrendsSelection } from './trends/use-trends-selection';

const CohortQuery = createQueryState({ formatError: cohortErrorMessage });

export interface CohortTrendsPanelProps {
  panelId: string;
  tabId: string;
}

function CohortTrendsBody({ panelId, tabId }: CohortTrendsPanelProps) {
  const { trendsQuery } = useTrendsSelection();

  return (
    <section
      id={panelId}
      role="tabpanel"
      aria-labelledby={tabId}
      aria-label="Compatible PO-set trend comparison"
      className="space-y-5"
    >
      <TrendsSnapshotPicker />

      <CohortQuery query={trendsQuery}>
        <CohortQuery.Loading>
          <div className="space-y-3" role="status">
            <p className="text-sm text-muted-foreground">
              Loading compatible PO-set trends…
            </p>
            <Skeleton className="h-52 w-full" />
          </div>
        </CohortQuery.Loading>

        <CohortQuery.Error title="Trend comparison unavailable" />

        <CohortQuery.Ready>
          {(trendsData: CohortTrendsResponse) => (
            <div className="space-y-4">
              <TrendsOutcomeChart
                poSetVersion={trendsData.po_set_version}
                points={trendsData.points}
              />
              <TrendsComparisonTable
                poSetVersion={trendsData.po_set_version}
                points={trendsData.points}
              />
            </div>
          )}
        </CohortQuery.Ready>
      </CohortQuery>
    </section>
  );
}

/**
 * Thin Chronological Trends orchestrator backed by a per-mount Zustand
 * context store (`TrendsStoreProvider`) for fine-grained subscriptions and
 * zero prop drilling.
 */
export function CohortTrendsPanel(props: CohortTrendsPanelProps) {
  return (
    <TrendsStoreProvider>
      <CohortTrendsBody {...props} />
    </TrendsStoreProvider>
  );
}
