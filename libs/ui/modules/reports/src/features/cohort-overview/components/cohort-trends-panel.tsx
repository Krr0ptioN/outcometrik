'use client';

import { memo, useCallback, useId, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  NativeSelect,
  NativeSelectOption,
  NotAssessedText,
  Skeleton,
  StaleTag,
  StatusDot,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  createQueryState,
} from '@outcometrik/ui';
import { cohortErrorMessage, formatCoveragePercent, shortRef } from '../api';
import { useCohortTrendsQuery } from '../hooks/use-cohort-overview';
import type {
  CohortTrendPoint,
  CohortTrendsResponse,
} from '../types';
import { parseNumericScore } from './cohort-formatters';
import { useCohortOverviewContext } from './cohort-overview-context';

const CohortQuery = createQueryState({ formatError: cohortErrorMessage });
const GRID_TICKS = [0, 25, 50, 70, 85, 100] as const;

const TrendAreaChart = memo(function TrendAreaChart({
  points,
  selectedCode,
}: {
  points: CohortTrendPoint[];
  selectedCode: string;
}) {
  const gradientId = useId();
  const width = 640;
  const height = 220;
  const padLeft = 40;
  const padRight = 24;
  const padTop = 20;
  const padBottom = 38;
  const innerW = width - padLeft - padRight;
  const innerH = height - padTop - padBottom;

  const series = useMemo(
    () =>
      points.map((point, index) => {
        const match = point.outcomes.find((o) => o.code === selectedCode);
        const val = match && match.n > 0 ? parseNumericScore(match.mean) : null;
        const x =
          points.length === 1
            ? padLeft + innerW / 2
            : padLeft + (index / (points.length - 1)) * innerW;
        const y = val === null ? null : padTop + innerH - (val / 100) * innerH;
        const label = point.term?.label ?? `Series v${point.series_version}`;
        return {
          id: point.publication_id,
          label,
          value: val,
          rawMean: match?.mean ?? null,
          x,
          y,
        };
      }),
    [points, selectedCode, innerW, innerH],
  );

  const validPoints = series.filter(
    (pt): pt is typeof pt & { y: number; value: number } => pt.y !== null,
  );

  const linePath =
    validPoints.length > 0
      ? validPoints
          .map(
            (pt, i) =>
              `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`,
          )
          .join(' ')
      : '';

  const areaPath =
    validPoints.length > 1
      ? `${linePath} L ${validPoints[validPoints.length - 1].x.toFixed(1)} ${(padTop + innerH).toFixed(1)} L ${validPoints[0].x.toFixed(1)} ${(padTop + innerH).toFixed(1)} Z`
      : '';

  return (
    <div className="rounded-[var(--radius-card,10px)] border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-foreground">
            {selectedCode} attainment trend (0–100 scale)
          </h4>
          <p className="text-xs text-muted-foreground">
            Chronological mean across compatible PO-Set snapshots. Dashed rule
            marks 70.0 target threshold.
          </p>
        </div>
      </div>

      {validPoints.length === 0 ? (
        <div className="flex h-36 items-center justify-center rounded-md border border-dashed bg-muted/30">
          <NotAssessedText label="— Not assessed across selected snapshots" />
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-56 w-full overflow-visible"
          role="img"
          aria-label={`${selectedCode} chronological trend chart across ${points.length} publications`}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop
                offset="0%"
                stopColor="var(--accent-primary)"
                stopOpacity="0.16"
              />
              <stop
                offset="100%"
                stopColor="var(--accent-primary)"
                stopOpacity="0"
              />
            </linearGradient>
          </defs>

          {GRID_TICKS.map((tick) => {
            const y = padTop + innerH - (tick / 100) * innerH;
            const isTarget = tick === 70;
            return (
              <g key={tick}>
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke={
                    isTarget
                      ? 'var(--accent-primary)'
                      : 'var(--border-hairline)'
                  }
                  strokeOpacity={isTarget ? 0.45 : 1}
                  strokeDasharray={isTarget ? '4 4' : undefined}
                  strokeWidth={1}
                />
                <text
                  x={padLeft - 8}
                  y={y + 4}
                  textAnchor="end"
                  className="fill-muted-foreground text-[10px]"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {tick}
                </text>
              </g>
            );
          })}

          {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}

          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke="var(--accent-primary)"
              strokeWidth={2.25}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {series.map((pt) => (
            <g key={pt.id}>
              <text
                x={pt.x}
                y={height - 10}
                textAnchor="middle"
                className="fill-muted-foreground text-[11px]"
              >
                {pt.label}
              </text>
              {pt.y !== null && pt.value !== null ? (
                <>
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={4.5}
                    fill="var(--surface-raised)"
                    stroke="var(--accent-primary)"
                    strokeWidth={2.25}
                  />
                  <text
                    x={pt.x}
                    y={Math.max(12, pt.y - 10)}
                    textAnchor="middle"
                    className="fill-foreground text-[11px] font-semibold"
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {pt.rawMean ?? pt.value.toFixed(1)}
                  </text>
                </>
              ) : (
                <text
                  x={pt.x}
                  y={padTop + innerH - 8}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[10px]"
                >
                  —
                </text>
              )}
            </g>
          ))}
        </svg>
      )}
    </div>
  );
});

export interface CohortTrendsPanelProps {
  panelId: string;
  tabId: string;
}

/**
 * Isolated Chronological Trends panel reading shared program/publications
 * from `CohortOverviewContext` (zero prop drilling) while owning its own
 * snapshot selection, PO dropdown state, and trends query.
 */
export function CohortTrendsPanel({
  panelId,
  tabId,
}: CohortTrendsPanelProps) {
  const {
    activeProgramId: programId,
    publications,
    activePoSetVersion,
  } = useCohortOverviewContext();
  const trendPoSelectId = useId();
  const [customTrendPubIds, setCustomTrendPubIds] = useState<string[] | null>(
    null,
  );
  const [selectedTrendPoCode, setSelectedTrendPoCode] = useState<string>('');

  const compatiblePublications = useMemo(
    () =>
      activePoSetVersion !== undefined
        ? publications.filter((p) => p.po_set_version === activePoSetVersion)
        : [],
    [publications, activePoSetVersion],
  );

  const publicationIdSet = useMemo(
    () => new Set(publications.map((pub) => pub.id)),
    [publications],
  );

  const selectedTrendPublicationIds = useMemo(() => {
    if (customTrendPubIds !== null) {
      return customTrendPubIds.filter((id) => publicationIdSet.has(id));
    }
    return compatiblePublications.map((p) => p.id);
  }, [customTrendPubIds, publicationIdSet, compatiblePublications]);

  const selectedIdSet = useMemo(
    () => new Set(selectedTrendPublicationIds),
    [selectedTrendPublicationIds],
  );

  const hasIncompatibleTrendSelection = useMemo(() => {
    const versions = new Set<number>();
    for (const pub of publications) {
      if (selectedIdSet.has(pub.id)) {
        versions.add(pub.po_set_version);
      }
    }
    return versions.size > 1;
  }, [publications, selectedIdSet]);

  const trendsQuery = useCohortTrendsQuery(
    {
      programId,
      poSetVersion: customTrendPubIds === null ? activePoSetVersion : undefined,
      publicationIds:
        selectedTrendPublicationIds.length > 0
          ? selectedTrendPublicationIds
          : undefined,
    },
    Boolean(programId),
  );

  const availableTrendPoCodes = useMemo(() => {
    const firstPoint = trendsQuery.data?.points[0];
    if (!firstPoint) return [];
    return firstPoint.outcomes.map((o) => ({ code: o.code, label: o.label }));
  }, [trendsQuery.data]);

  const activeTrendPoCode =
    selectedTrendPoCode &&
    availableTrendPoCodes.some((o) => o.code === selectedTrendPoCode)
      ? selectedTrendPoCode
      : (availableTrendPoCodes[0]?.code ?? '');

  const toggleTrendPublication = useCallback(
    (pubId: string) => {
      setCustomTrendPubIds((prev) => {
        const current =
          prev !== null ? prev : compatiblePublications.map((p) => p.id);
        return current.includes(pubId)
          ? current.filter((id) => id !== pubId)
          : [...current, pubId];
      });
    },
    [compatiblePublications],
  );

  return (
    <section
      id={panelId}
      role="tabpanel"
      aria-labelledby={tabId}
      aria-label="Compatible PO-set trend comparison"
      className="space-y-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3
            id="po-trends-title"
            className="text-base font-semibold tracking-tight"
          >
            Compatible PO-set trend comparison
          </h3>
          <p className="text-xs text-muted-foreground">
            Only publications sharing the same PO-set version can be compared
            chronologically. Including a snapshot from a different PO-set
            triggers the server compatibility guard.
          </p>
        </div>
        {customTrendPubIds !== null && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setCustomTrendPubIds(null)}
            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Reset to compatible PO-Set v{activePoSetVersion ?? '?'}
          </Button>
        )}
      </div>

      {publications.length > 0 && (
        <fieldset className="space-y-2 rounded-[var(--radius-card,10px)] border border-border/80 bg-[var(--surface-subtle)]/40 p-3.5">
          <legend className="px-1 text-xs font-medium text-muted-foreground">
            Snapshots included in comparison
          </legend>
          <div className="flex flex-wrap gap-2">
            {publications.map((pub) => {
              const checked = selectedIdSet.has(pub.id);
              const isDifferentSet =
                activePoSetVersion !== undefined &&
                pub.po_set_version !== activePoSetVersion;
              return (
                <label
                  key={pub.id}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-[var(--radius-input,6px)] border px-2.5 py-1.5 text-xs transition-colors duration-150 ${
                    checked
                      ? 'border-[var(--accent-border)] bg-[var(--accent-soft)] text-foreground'
                      : 'border-border bg-card text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleTrendPublication(pub.id)}
                    className="accent-[var(--accent-primary)]"
                  />
                  <span className="tabular-mono font-medium">
                    Series v{pub.series_version}
                  </span>
                  <Badge
                    variant={isDifferentSet ? 'outline' : 'secondary'}
                    className="tabular-mono px-1.5 py-0 text-[11px]"
                  >
                    PO-Set v{pub.po_set_version}
                  </Badge>
                  {pub.stale && <StaleTag label="STALE" />}
                </label>
              );
            })}
          </div>
          {hasIncompatibleTrendSelection && (
            <p className="text-xs text-[var(--status-warn-fg)]">
              Selected snapshots span multiple PO-Set versions; requesting
              comparison will be rejected by the server compatibility guard.
            </p>
          )}
        </fieldset>
      )}

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
              {availableTrendPoCodes.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor={trendPoSelectId}
                      className="text-xs font-medium text-muted-foreground"
                    >
                      Chart outcome
                    </label>
                    <NativeSelect
                      id={trendPoSelectId}
                      value={activeTrendPoCode}
                      onChange={(e) => setSelectedTrendPoCode(e.target.value)}
                      className="h-8 w-56 bg-card text-xs"
                    >
                      {availableTrendPoCodes.map((po) => (
                        <NativeSelectOption key={po.code} value={po.code}>
                          {po.code} · {po.label}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  </div>
                  <Badge variant="secondary" className="tabular-mono">
                    PO-Set v{trendsData.po_set_version} ·{' '}
                    {trendsData.points.length} snapshot
                    {trendsData.points.length === 1 ? '' : 's'}
                  </Badge>
                </div>
              )}

              {activeTrendPoCode && trendsData.points.length > 0 && (
                <TrendAreaChart
                  points={trendsData.points}
                  selectedCode={activeTrendPoCode}
                />
              )}

              <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                <Table>
                  <TableCaption className="pb-3">
                    Trend comparison across compatible publications for PO-Set v
                    {trendsData.po_set_version}.
                  </TableCaption>
                  <TableHeader className="bg-[var(--surface-subtle)]">
                    <TableRow>
                      <TableHead scope="col">Snapshot</TableHead>
                      <TableHead scope="col">PO-Set</TableHead>
                      <TableHead scope="col">Status</TableHead>
                      <TableHead scope="col" className="text-right">
                        Sample (n / population)
                      </TableHead>
                      <TableHead scope="col" className="text-right">
                        Coverage
                      </TableHead>
                      <TableHead scope="col">PO means</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {trendsData.points.map((point) => (
                      <TableRow key={point.publication_id}>
                        <th
                          scope="row"
                          className="p-2.5 text-left align-middle font-medium whitespace-nowrap"
                        >
                          {point.term?.label ?? shortRef(point.publication_id)}
                          <span className="tabular-mono block text-xs font-normal text-muted-foreground">
                            Pub {shortRef(point.publication_id)} · Series v
                            {point.series_version}
                          </span>
                        </th>
                        <TableCell className="tabular-mono">
                          v{point.po_set_version}
                        </TableCell>
                        <TableCell>
                          {point.publication_status === 'stale' ? (
                            <StaleTag label="Stale" />
                          ) : (
                            <StatusDot variant="success" label="Published" />
                          )}
                        </TableCell>
                        <TableCell className="tabular-mono text-right">
                          {point.sample_size} / {point.population_size}
                        </TableCell>
                        <TableCell className="tabular-mono text-right">
                          {formatCoveragePercent(point.coverage)}
                        </TableCell>
                        <TableCell className="tabular-mono text-xs">
                          {point.outcomes
                            .map(
                              (o) =>
                                `${o.code}: ${o.n > 0 && o.mean !== null ? o.mean : '—'} (n=${o.n})`,
                            )
                            .join(' · ')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </CohortQuery.Ready>
      </CohortQuery>
    </section>
  );
}
