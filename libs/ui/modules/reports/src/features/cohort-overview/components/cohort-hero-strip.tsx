'use client';

import { memo, useId, useMemo } from 'react';
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
import {
  formatExclusionParts,
  parseNumericScore,
  totalExclusionsCount,
} from './cohort-formatters';

export interface CohortHeroStripProps {
  analytics: CohortAnalyticsResponse;
}

/**
 * Asymmetric Hero + Supporting Insights + Traceability Strip.
 * Follows ui-craft dashboard hierarchy: one accent-tinted hero metric with
 * a 32px inline SVG sparkline, flanked by neutral supporting context and a
 * compact publication traceability ledger (no equal-weight KPI card grid).
 */
export const CohortHeroStrip = memo(function CohortHeroStrip({
  analytics,
}: CohortHeroStripProps) {
  const sparkGradientId = useId();

  const summary = useMemo(() => {
    const measuredScores: number[] = [];
    let aboveTarget = 0;
    let belowTarget = 0;
    for (const outcome of analytics.outcomes) {
      if (outcome.n > 0 && outcome.mean !== null) {
        const val = parseNumericScore(outcome.mean);
        if (val !== null) {
          measuredScores.push(val);
          if (val >= 70) aboveTarget += 1;
          else belowTarget += 1;
        }
      }
    }
    const avgMean =
      measuredScores.length > 0
        ? measuredScores.reduce((sum, v) => sum + v, 0) / measuredScores.length
        : null;
    return {
      measuredScores,
      measuredCount: measuredScores.length,
      totalCount: analytics.outcomes.length,
      avgMean,
      aboveTarget,
      belowTarget,
    };
  }, [analytics.outcomes]);

  const coverageRatio = Math.max(
    0,
    Math.min(100, Math.round(Number(analytics.coverage) * 1000) / 10 || 0),
  );
  const exclusionTotal = totalExclusionsCount(analytics.exclusions);
  const exclusionParts = formatExclusionParts(analytics.exclusions);

  // Build 32px inline SVG sparkline path across measured PO means
  const sparkPath = useMemo(() => {
    const pts = summary.measuredScores;
    if (pts.length === 0) return { line: '', area: '' };
    const w = 96;
    const h = 32;
    const coords = pts.map((val, idx) => {
      const x = pts.length === 1 ? w / 2 : (idx / (pts.length - 1)) * w;
      const y = h - 3 - (val / 100) * (h - 6);
      return { x, y };
    });
    const line = coords
      .map(
        (c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`,
      )
      .join(' ');
    const area =
      coords.length > 1
        ? `${line} L ${coords[coords.length - 1].x.toFixed(1)} ${h} L ${coords[0].x.toFixed(1)} ${h} Z`
        : '';
    return { line, area };
  }, [summary.measuredScores]);

  return (
    <section
      aria-label="Publication summary and traceability metadata"
      className="space-y-3"
    >
      <div className="grid gap-4 lg:grid-cols-12">
        {/* Hero Metric Card (accent-tinted, 5 cols) */}
        <div className="flex flex-col justify-between gap-3 rounded-[var(--radius-card,10px)] border border-[var(--accent-border)] bg-[var(--accent-soft)]/55 p-4 lg:col-span-5">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">
                Cohort mean attainment
              </p>
              <div className="flex items-baseline gap-2">
                <span className="tabular-mono text-[32px] leading-none font-semibold tracking-tight text-foreground">
                  {summary.avgMean !== null
                    ? summary.avgMean.toFixed(1)
                    : '—'}
                </span>
                {summary.avgMean !== null && (
                  <span className="tabular-mono text-xs text-muted-foreground">
                    / 100
                  </span>
                )}
              </div>
            </div>

            {sparkPath.line && (
              <svg
                width={96}
                height={32}
                viewBox="0 0 96 32"
                className="shrink-0 overflow-visible"
                aria-hidden="true"
              >
                <defs>
                  <linearGradient
                    id={sparkGradientId}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="var(--accent-primary)"
                      stopOpacity="0.22"
                    />
                    <stop
                      offset="100%"
                      stopColor="var(--accent-primary)"
                      stopOpacity="0"
                    />
                  </linearGradient>
                </defs>
                {sparkPath.area && (
                  <path
                    d={sparkPath.area}
                    fill={`url(#${sparkGradientId})`}
                  />
                )}
                <path
                  d={sparkPath.line}
                  fill="none"
                  stroke="var(--accent-primary)"
                  strokeWidth={1.75}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>

          <p className="text-xs text-muted-foreground">
            <span className="tabular-mono font-medium text-foreground">
              {summary.measuredCount} / {summary.totalCount}
            </span>{' '}
            outcomes assessed ·{' '}
            <span className="tabular-mono font-medium text-foreground">
              {summary.aboveTarget}
            </span>{' '}
            meeting ≥70.0 target
            {summary.belowTarget > 0
              ? ` · ${summary.belowTarget} below target`
              : ''}
          </p>
        </div>

        {/* Supporting Coverage Card (neutral, 3 cols) */}
        <div className="flex flex-col justify-between gap-3 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 lg:col-span-3">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Measurement coverage
            </p>
            <p className="tabular-mono text-2xl leading-none font-semibold text-foreground">
              {formatCoveragePercent(analytics.coverage)}
            </p>
          </div>
          <div className="space-y-1.5">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-subtle)]">
              <div
                className="h-full rounded-full bg-[var(--accent-primary)]"
                style={{ width: `${coverageRatio}%` }}
              />
            </div>
            <p className="tabular-mono text-xs text-muted-foreground">
              n = {analytics.sample_size} / {analytics.population_size} ·{' '}
              {exclusionTotal} excluded
            </p>
          </div>
        </div>

        {/* Compact Traceability Proof Ledger (neutral, 4 cols) */}
        <div className="flex flex-col justify-between gap-2.5 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 lg:col-span-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {analytics.publication_status === 'stale' ? (
              <>
                <StaleTag label="STALE" />
                <span className="sr-only">Stale</span>
              </>
            ) : (
              <StatusDot variant="success" label="Published" />
            )}
            <div className="flex items-center gap-1.5">
              <Badge variant="secondary" className="tabular-mono text-[11px]">
                Series v{analytics.series_version}
              </Badge>
              <Badge variant="secondary" className="tabular-mono text-[11px]">
                PO-Set v{analytics.po_set_version}
              </Badge>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
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
            <Badge variant="outline" className="tabular-mono bg-card">
              Policy {analytics.policy_version}
            </Badge>
          </div>

          <p className="truncate text-[11px] text-muted-foreground" title={analytics.publication_id}>
            ID: <code className="tabular-mono text-foreground">{analytics.publication_id}</code>
            {exclusionParts.length > 0 && ` · ${exclusionParts.join(', ')}`}
          </p>
        </div>
      </div>

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
