'use client';

import { memo } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  StaleTag,
  StatusDot,
} from '@outcometrik/ui';
import { formatCoveragePercent, shortRef } from '../api';
import type { CohortAnalyticsResponse } from '../types';
import { formatExclusionParts, totalExclusionsCount } from './cohort-formatters';

export interface CohortTraceabilityHeaderProps {
  analytics: CohortAnalyticsResponse;
}

export const CohortTraceabilityHeader = memo(function CohortTraceabilityHeader({
  analytics,
}: CohortTraceabilityHeaderProps) {
  return (
    <section
      aria-label="Publication traceability metadata"
      className="space-y-3 rounded-[var(--radius-card,10px)] border border-[var(--accent-border)] bg-[var(--accent-soft)]/45 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {analytics.publication_status === 'stale' ? (
            <>
              <StaleTag label="STALE" />
              <span className="sr-only">Stale</span>
            </>
          ) : (
            <StatusDot variant="success" label="Published" />
          )}
          <Badge
            variant="outline"
            className="tabular-mono bg-card"
            title={analytics.publication_id}
          >
            Publication {shortRef(analytics.publication_id)}
          </Badge>
          <Badge
            variant="outline"
            className="tabular-mono bg-card"
            title={analytics.run_id}
          >
            Run {shortRef(analytics.run_id)}
          </Badge>
          <Badge variant="secondary" className="tabular-mono">
            Series v{analytics.series_version}
          </Badge>
          <Badge variant="secondary" className="tabular-mono">
            PO-Set v{analytics.po_set_version}
          </Badge>
          <Badge variant="outline" className="tabular-mono bg-card">
            Policy {analytics.policy_version}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span className="tabular-mono font-medium text-foreground">
            n = {analytics.sample_size} / {analytics.population_size}
          </span>
          <span className="tabular-mono font-semibold text-[var(--accent-primary)]">
            {formatCoveragePercent(analytics.coverage)} coverage
          </span>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Publication ID:{' '}
        <code className="tabular-mono text-foreground">
          {analytics.publication_id}
        </code>{' '}
        · Series v{analytics.series_version} · Total exclusions:{' '}
        <span className="tabular-mono font-medium text-foreground">
          {totalExclusionsCount(analytics.exclusions)}
        </span>{' '}
        ({formatExclusionParts(analytics.exclusions).join(', ') || 'None'})
      </p>

      {analytics.publication_status === 'stale' && (
        <Alert variant="destructive">
          <AlertTitle>Stale publication snapshot</AlertTitle>
          <AlertDescription>
            Underlying grades or syllabus mappings changed after this snapshot
            was published. Values below remain immutable; recalculate and
            publish a new snapshot to reflect updates.
          </AlertDescription>
        </Alert>
      )}
    </section>
  );
});
