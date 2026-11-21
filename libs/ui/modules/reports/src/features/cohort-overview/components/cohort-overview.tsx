'use client';

import { useEffect, useId, useMemo, useState } from 'react';
import { ApiError } from '@outcometrik/api';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldGroup,
  FieldLabel,
  MeasuredZeroTag,
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
} from '@outcometrik/ui';
import { cohortErrorMessage, formatCoveragePercent, shortRef } from '../api';
import { PoAttainmentBarChart } from './po-attainment-chart';
import {
  useCohortAnalyticsQuery,
  useCohortCoursesQuery,
  useCohortTermsQuery,
  useCohortTrendsQuery,
  useCoordinatorProgramsQuery,
  useCoordinatorPublicationsQuery,
} from '../hooks/use-cohort-overview';
import type {
  CohortCourseOption,
  CohortDistribution,
  CohortExclusions,
  CohortOutcomeMetric,
  CohortProgramOption,
  CohortTermOption,
  CohortTrendPoint,
  CoordinatorPublication,
} from '../types';

export interface CohortSelection {
  programId: string | null;
  publicationId: string | null;
  termId?: string | null;
  courseId?: string | null;
}

export type CohortOverviewTab = 'overview' | 'trends';

export interface CohortFilterValues {
  programId: string;
  publicationId: string;
  termId: string;
  courseId: string;
}

export interface CohortOverviewProps {
  /** Authorized programs; fetched from /api/v1/programs/ when omitted. */
  programs?: CohortProgramOption[];
  /** Optional term filter options; fetched from /api/v1/terms/ when omitted. */
  terms?: CohortTermOption[];
  /** Optional course filter options; fetched from /api/v1/courses/ when omitted. */
  courses?: CohortCourseOption[];
  /** Initial program selection (uncontrolled mode). */
  defaultProgramId?: string;
  /** Initial publication selection (uncontrolled mode). */
  defaultPublicationId?: string;
  /** Initial term filter (uncontrolled mode). */
  defaultTermId?: string;
  /** Initial course filter (uncontrolled mode). */
  defaultCourseId?: string;
  /** Controlled program selection (for URL-synced routes). */
  programId?: string;
  /** Controlled publication selection (for URL-synced routes). */
  publicationId?: string;
  /** Controlled term filter (for URL-synced routes). */
  termId?: string;
  /** Controlled course filter (for URL-synced routes). */
  courseId?: string;
  /** Controlled active tab ('overview' | 'trends'). */
  activeTab?: CohortOverviewTab;
  /** Whether to open the Chronological Trends tab by default. */
  defaultShowTrends?: boolean;
  /** Notified whenever any filter value changes (for URL query synchronization). */
  onFiltersChange?: (filters: CohortFilterValues) => void;
  /** Notified whenever the active tab changes. */
  onTabChange?: (tab: CohortOverviewTab) => void;
  /** Notified whenever the active program or publication changes. */
  onSelectionChange?: (selection: CohortSelection) => void;
}

/**
 * Single-hue Institutional Navy opacity ramp for the 4 attainment bands:
 * 85-100 = 100% navy, 70-84.9 = 62% navy, 50-69.9 = 32% navy, <50 = danger.
 */
export const BUCKET_META: ReadonlyArray<{
  key: keyof CohortDistribution;
  label: string;
  barClass: string;
  swatchClass: string;
}> = [
  {
    key: '<50',
    label: '<50',
    barClass: 'bg-[var(--status-danger-fg)]',
    swatchClass: 'bg-[var(--status-danger-fg)]',
  },
  {
    key: '50-69.9',
    label: '50–69.9',
    barClass: 'bg-[color-mix(in_oklch,var(--accent-primary)_32%,transparent)]',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_32%,transparent)]',
  },
  {
    key: '70-84.9',
    label: '70–84.9',
    barClass: 'bg-[color-mix(in_oklch,var(--accent-primary)_62%,transparent)]',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_62%,transparent)]',
  },
  {
    key: '85-100',
    label: '85–100',
    barClass: 'bg-[var(--accent-primary)]',
    swatchClass: 'bg-[var(--accent-primary)]',
  },
];

export function formatExclusionParts(exclusions: CohortExclusions): string[] {
  const parts: string[] = [];
  if (exclusions.NOT_ASSESSED > 0) {
    parts.push(`Not assessed: ${exclusions.NOT_ASSESSED}`);
  }
  if (exclusions.INCOMPLETE > 0) {
    parts.push(`Incomplete: ${exclusions.INCOMPLETE}`);
  }
  if (exclusions.ALL_EXEMPT > 0) {
    parts.push(`Exempt: ${exclusions.ALL_EXEMPT}`);
  }
  if (exclusions.UNMAPPED > 0) {
    parts.push(`Unmapped: ${exclusions.UNMAPPED}`);
  }
  return parts;
}

export function totalExclusionsCount(exclusions: CohortExclusions): number {
  return (
    exclusions.NOT_ASSESSED +
    exclusions.INCOMPLETE +
    exclusions.ALL_EXEMPT +
    exclusions.UNMAPPED
  );
}

function formatPublicationLabel(pub: CoordinatorPublication): string {
  const datePart = pub.published_at ? pub.published_at.slice(0, 10) : 'Draft';
  const statusPart = pub.stale ? 'Stale' : 'Published';
  return `Series v${pub.series_version} · PO-Set v${pub.po_set_version} · ${datePart} (${statusPart}) · ${shortRef(pub.id)}`;
}

function formatMinMax(outcome: CohortOutcomeMetric): string {
  if (outcome.n === 0 || outcome.min === null || outcome.max === null) {
    return '—';
  }
  return `${outcome.min}–${outcome.max}`;
}

function isMeasuredZero(outcome: CohortOutcomeMetric): boolean {
  if (outcome.n === 0 || outcome.mean === null) return false;
  const parsed = Number(outcome.mean);
  return Number.isFinite(parsed) && parsed === 0;
}

function parseNumericScore(value: string | null): number | null {
  if (value === null) return null;
  const num = Number(value);
  return Number.isFinite(num) ? Math.max(0, Math.min(100, num)) : null;
}

function TrendAreaChart({
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

  const series = points.map((point, index) => {
    const match = point.outcomes.find((o) => o.code === selectedCode);
    const val = match && match.n > 0 ? parseNumericScore(match.mean) : null;
    const x =
      points.length === 1
        ? padLeft + innerW / 2
        : padLeft + (index / (points.length - 1)) * innerW;
    const y = val === null ? null : padTop + innerH - (val / 100) * innerH;
    const label =
      point.term?.label ?? `Series v${point.series_version}`;
    return {
      id: point.publication_id,
      label,
      value: val,
      rawMean: match?.mean ?? null,
      n: match?.n ?? 0,
      x,
      y,
    };
  });

  const validPoints = series.filter(
    (pt): pt is typeof pt & { y: number; value: number } => pt.y !== null,
  );

  const linePath =
    validPoints.length > 0
      ? validPoints
          .map((pt, i) => `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`)
          .join(' ')
      : '';

  const areaPath =
    validPoints.length > 1
      ? `${linePath} L ${validPoints[validPoints.length - 1].x.toFixed(1)} ${(padTop + innerH).toFixed(1)} L ${validPoints[0].x.toFixed(1)} ${(padTop + innerH).toFixed(1)} Z`
      : '';

  const gridTicks = [0, 25, 50, 70, 85, 100];

  return (
    <div className="rounded-[var(--radius-card,10px)] border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-foreground">
            {selectedCode} attainment trend (0–100 scale)
          </h4>
          <p className="text-xs text-muted-foreground">
            Chronological mean across compatible PO-Set snapshots. Dashed rule marks 70.0 target threshold.
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

          {/* Horizontal-only gridlines */}
          {gridTicks.map((tick) => {
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

          {/* Area fill (15% -> 0%) */}
          {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}

          {/* Primary trend line */}
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

          {/* Direct-labeled data points */}
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
}

export function CohortOverview({
  programs: providedPrograms,
  terms: providedTerms,
  courses: providedCourses,
  defaultProgramId,
  defaultPublicationId,
  defaultTermId = '',
  defaultCourseId = '',
  programId: controlledProgramId,
  publicationId: controlledPublicationId,
  termId: controlledTermId,
  courseId: controlledCourseId,
  activeTab: controlledTab,
  defaultShowTrends = false,
  onFiltersChange,
  onTabChange,
  onSelectionChange,
}: CohortOverviewProps) {
  const programSelectId = useId();
  const publicationSelectId = useId();
  const termSelectId = useId();
  const courseSelectId = useId();
  const trendPoSelectId = useId();
  const overviewTabId = useId();
  const trendsTabId = useId();
  const overviewPanelId = useId();
  const trendsPanelId = useId();

  const programsQuery = useCoordinatorProgramsQuery(
    providedPrograms === undefined,
  );
  const termsQuery = useCohortTermsQuery(providedTerms === undefined);
  const coursesQuery = useCohortCoursesQuery(providedCourses === undefined);

  const programs = providedPrograms ?? programsQuery.data ?? [];
  const terms = providedTerms ?? termsQuery.data ?? [];
  const courses = providedCourses ?? coursesQuery.data ?? [];

  const [internalProgramId, setInternalProgramId] = useState<string>(
    defaultProgramId ?? '',
  );
  const [internalPublicationId, setInternalPublicationId] = useState<string>(
    defaultPublicationId ?? '',
  );
  const [internalTermId, setInternalTermId] = useState<string>(defaultTermId);
  const [internalCourseId, setInternalCourseId] =
    useState<string>(defaultCourseId);
  const [internalTab, setInternalTab] = useState<CohortOverviewTab>(
    defaultShowTrends ? 'trends' : 'overview',
  );
  const [customTrendPubIds, setCustomTrendPubIds] = useState<string[] | null>(
    null,
  );
  const [selectedTrendPoCode, setSelectedTrendPoCode] = useState<string>('');

  const selectedProgramId = controlledProgramId ?? internalProgramId;
  const selectedPublicationId = controlledPublicationId ?? internalPublicationId;
  const selectedTermId = controlledTermId ?? internalTermId;
  const selectedCourseId = controlledCourseId ?? internalCourseId;
  const activeTab: CohortOverviewTab = controlledTab ?? internalTab;
  const showTrends = activeTab === 'trends';

  const activeProgramId =
    selectedProgramId && programs.some((p) => p.id === selectedProgramId)
      ? selectedProgramId
      : (programs[0]?.id ?? '');

  const publicationsQuery = useCoordinatorPublicationsQuery(
    activeProgramId || null,
    Boolean(activeProgramId),
  );
  const publications = publicationsQuery.data ?? [];

  const activePublicationId =
    selectedPublicationId &&
    publications.some((pub) => pub.id === selectedPublicationId)
      ? selectedPublicationId
      : (publications[0]?.id ?? '');

  const analyticsQuery = useCohortAnalyticsQuery(
    activeProgramId
      ? {
          programId: activeProgramId,
          publicationId: activePublicationId || undefined,
          termId: selectedTermId || undefined,
          courseId: selectedCourseId || undefined,
        }
      : null,
    Boolean(activeProgramId),
  );

  const analytics = analyticsQuery.data ?? null;
  const resolvedPublicationId =
    analytics?.publication_id ?? (activePublicationId || null);

  const activePoSetVersion =
    analytics?.po_set_version ??
    publications.find((p) => p.id === activePublicationId)?.po_set_version;

  const compatiblePublications = useMemo(
    () =>
      activePoSetVersion !== undefined
        ? publications.filter((p) => p.po_set_version === activePoSetVersion)
        : [],
    [publications, activePoSetVersion],
  );

  const selectedTrendPublicationIds = useMemo(() => {
    if (customTrendPubIds !== null) {
      return customTrendPubIds.filter((id) =>
        publications.some((pub) => pub.id === id),
      );
    }
    return compatiblePublications.map((p) => p.id);
  }, [customTrendPubIds, publications, compatiblePublications]);

  const hasIncompatibleTrendSelection = useMemo(() => {
    const selectedPubs = publications.filter((p) =>
      selectedTrendPublicationIds.includes(p.id),
    );
    const versions = new Set(selectedPubs.map((p) => p.po_set_version));
    return versions.size > 1;
  }, [publications, selectedTrendPublicationIds]);

  const trendsQuery = useCohortTrendsQuery(
    activeProgramId
      ? {
          programId: activeProgramId,
          // Omit poSetVersion when user explicitly picks publications so backend validates compatibility and returns HTTP 400 incompatible_po_set_version
          poSetVersion:
            customTrendPubIds === null ? activePoSetVersion : undefined,
          publicationIds:
            selectedTrendPublicationIds.length > 0
              ? selectedTrendPublicationIds
              : undefined,
        }
      : null,
    showTrends && Boolean(activeProgramId),
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

  function updateFilters(patch: Partial<CohortFilterValues>) {
    const next: CohortFilterValues = {
      programId: patch.programId ?? activeProgramId,
      publicationId:
        patch.publicationId !== undefined
          ? patch.publicationId
          : selectedPublicationId,
      termId: patch.termId !== undefined ? patch.termId : selectedTermId,
      courseId: patch.courseId !== undefined ? patch.courseId : selectedCourseId,
    };
    if (controlledProgramId === undefined) setInternalProgramId(next.programId);
    if (controlledPublicationId === undefined)
      setInternalPublicationId(next.publicationId);
    if (controlledTermId === undefined) setInternalTermId(next.termId);
    if (controlledCourseId === undefined) setInternalCourseId(next.courseId);
    if (patch.programId !== undefined && patch.programId !== activeProgramId) {
      setCustomTrendPubIds(null);
    }
    onFiltersChange?.(next);
  }

  function handleTabChange(nextTab: CohortOverviewTab) {
    if (controlledTab === undefined) setInternalTab(nextTab);
    onTabChange?.(nextTab);
  }

  function handleResetFilters() {
    updateFilters({
      publicationId: '',
      termId: '',
      courseId: '',
    });
  }

  function toggleTrendPublication(pubId: string) {
    const current =
      customTrendPubIds !== null
        ? customTrendPubIds
        : compatiblePublications.map((p) => p.id);
    const exists = current.includes(pubId);
    const next = exists
      ? current.filter((id) => id !== pubId)
      : [...current, pubId];
    setCustomTrendPubIds(next);
  }

  const hasActiveFilters =
    Boolean(selectedTermId) ||
    Boolean(selectedCourseId) ||
    (Boolean(selectedPublicationId) &&
      publications.length > 0 &&
      selectedPublicationId !== publications[0]?.id);

  useEffect(() => {
    onSelectionChange?.({
      programId: activeProgramId || null,
      publicationId: resolvedPublicationId,
      termId: selectedTermId || null,
      courseId: selectedCourseId || null,
    });
  }, [
    activeProgramId,
    resolvedPublicationId,
    selectedTermId,
    selectedCourseId,
    onSelectionChange,
  ]);

  const isNotFound =
    analyticsQuery.isError &&
    analyticsQuery.error instanceof ApiError &&
    analyticsQuery.error.status === 404;

  const isFatalAnalyticsError = analyticsQuery.isError && !isNotFound;

  return (
    <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
      <CardHeader className="border-b border-border/70 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle>
              <h2 className="text-lg font-semibold tracking-tight">
                Cohort outcome overview
              </h2>
            </CardTitle>
            <CardDescription>
              Published PO1–PO11 attainment, 4-band distributions, measurement
              coverage, and PO-set-safe chronological trends.
            </CardDescription>
          </div>

          <div
            role="tablist"
            aria-label="Cohort analytics views"
            className="inline-flex items-center rounded-[var(--radius-input,6px)] border border-border bg-muted/50 p-0.5"
          >
            <button
              id={overviewTabId}
              type="button"
              role="tab"
              aria-selected={activeTab === 'overview'}
              aria-controls={overviewPanelId}
              onClick={() => handleTabChange('overview')}
              className={`rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring ${
                activeTab === 'overview'
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Overview &amp; distributions
            </button>
            <button
              id={trendsTabId}
              type="button"
              role="tab"
              aria-selected={activeTab === 'trends'}
              aria-controls={trendsPanelId}
              disabled={!activeProgramId}
              onClick={() => handleTabChange('trends')}
              className={`rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 ${
                activeTab === 'trends'
                  ? 'bg-card text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Chronological trends
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-5">
        {providedPrograms === undefined && programsQuery.isPending && (
          <div className="space-y-2" role="status">
            <p className="text-sm text-muted-foreground">
              Loading authorized programs…
            </p>
            <Skeleton className="h-10 w-full" />
          </div>
        )}

        {providedPrograms === undefined && programsQuery.isError && (
          <Alert variant="destructive">
            <AlertTitle>Unable to load programs</AlertTitle>
            <AlertDescription>
              {cohortErrorMessage(programsQuery.error)}
            </AlertDescription>
          </Alert>
        )}

        {programs.length === 0 &&
          !programsQuery.isPending &&
          !programsQuery.isError && (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No published cohort analytics available</EmptyTitle>
                <EmptyDescription>
                  No authorized programs were found for your coordinator scope.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}

        {/* Filter bar with ghost styling + conditional Reset filters link */}
        {programs.length > 0 && (
          <div className="space-y-2">
            <FieldGroup className="grid gap-3 rounded-[var(--radius-card,10px)] border border-border/80 bg-[var(--surface-subtle)]/50 p-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field>
                <FieldLabel
                  htmlFor={programSelectId}
                  className="text-xs font-medium text-muted-foreground"
                >
                  Program
                </FieldLabel>
                <NativeSelect
                  id={programSelectId}
                  value={activeProgramId}
                  className="bg-card"
                  onChange={(event) => {
                    updateFilters({
                      programId: event.target.value,
                      publicationId: '',
                    });
                  }}
                >
                  {programs.map((program) => (
                    <NativeSelectOption key={program.id} value={program.id}>
                      {program.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel
                  htmlFor={publicationSelectId}
                  className="text-xs font-medium text-muted-foreground"
                >
                  Publication snapshot
                </FieldLabel>
                <NativeSelect
                  id={publicationSelectId}
                  value={activePublicationId}
                  className="bg-card"
                  disabled={
                    publicationsQuery.isPending || publications.length === 0
                  }
                  onChange={(event) =>
                    updateFilters({ publicationId: event.target.value })
                  }
                >
                  {publications.length === 0 ? (
                    <NativeSelectOption value="">
                      {publicationsQuery.isPending
                        ? 'Loading snapshots…'
                        : 'No published snapshots'}
                    </NativeSelectOption>
                  ) : (
                    publications.map((pub) => (
                      <NativeSelectOption key={pub.id} value={pub.id}>
                        {formatPublicationLabel(pub)}
                      </NativeSelectOption>
                    ))
                  )}
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel
                  htmlFor={termSelectId}
                  className="text-xs font-medium text-muted-foreground"
                >
                  Term
                </FieldLabel>
                <NativeSelect
                  id={termSelectId}
                  value={selectedTermId}
                  className="bg-card"
                  onChange={(event) =>
                    updateFilters({ termId: event.target.value })
                  }
                >
                  <NativeSelectOption value="">All terms</NativeSelectOption>
                  {terms.map((term) => (
                    <NativeSelectOption key={term.id} value={term.id}>
                      {term.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel
                  htmlFor={courseSelectId}
                  className="text-xs font-medium text-muted-foreground"
                >
                  Course
                </FieldLabel>
                <NativeSelect
                  id={courseSelectId}
                  value={selectedCourseId}
                  className="bg-card"
                  onChange={(event) =>
                    updateFilters({ courseId: event.target.value })
                  }
                >
                  <NativeSelectOption value="">All courses</NativeSelectOption>
                  {courses.map((course) => (
                    <NativeSelectOption key={course.id} value={course.id}>
                      {course.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
            </FieldGroup>

            {hasActiveFilters && (
              <div className="flex items-center justify-end">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleResetFilters}
                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  Reset filters
                </Button>
              </div>
            )}
          </div>
        )}

        {publicationsQuery.isError && (
          <Alert variant="destructive">
            <AlertTitle>Unable to load published snapshots</AlertTitle>
            <AlertDescription>
              {cohortErrorMessage(publicationsQuery.error)}
            </AlertDescription>
          </Alert>
        )}

        {/* OVERVIEW TAB PANEL */}
        {activeTab === 'overview' && (
          <div
            id={overviewPanelId}
            role="tabpanel"
            aria-labelledby={overviewTabId}
            className="space-y-6"
          >
            {activeProgramId && analyticsQuery.isPending && (
              <div className="space-y-3" role="status">
                <p className="text-sm text-muted-foreground">
                  Loading cohort analytics…
                </p>
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-56 w-full" />
              </div>
            )}

            {isFatalAnalyticsError && (
              <Alert variant="destructive">
                <AlertTitle>Unable to load cohort analytics</AlertTitle>
                <AlertDescription>
                  {cohortErrorMessage(analyticsQuery.error)}
                </AlertDescription>
              </Alert>
            )}

            {activeProgramId &&
              !analyticsQuery.isPending &&
              (isNotFound || (analytics && analytics.outcomes.length === 0)) && (
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>
                      No published cohort analytics available
                    </EmptyTitle>
                    <EmptyDescription>
                      Publish a calculation run for this program to inspect
                      cohort distributions and coverage.
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}

            {analytics && analytics.outcomes.length > 0 && (
              <>
                {/* Traceability Header */}
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
                      <Badge
                        variant="secondary"
                        className="tabular-mono"
                      >
                        Series v{analytics.series_version}
                      </Badge>
                      <Badge
                        variant="secondary"
                        className="tabular-mono"
                      >
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
                    (
                    {formatExclusionParts(analytics.exclusions).join(', ') ||
                      'None'}
                    )
                  </p>

                  {analytics.publication_status === 'stale' && (
                    <Alert variant="destructive">
                      <AlertTitle>Stale publication snapshot</AlertTitle>
                      <AlertDescription>
                        Underlying grades or syllabus mappings changed after
                        this snapshot was published. Values below remain
                        immutable; recalculate and publish a new snapshot to
                        reflect updates.
                      </AlertDescription>
                    </Alert>
                  )}
                </section>

                {/* PO1-PO11 Horizontal Attainment Bar Chart + Single-Hue 4-Band Ramp */}
                <section
                  aria-labelledby="po-distribution-chart-title"
                  className="space-y-4"
                >
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <h3
                        id="po-distribution-chart-title"
                        className="text-base font-semibold tracking-tight"
                      >
                        PO1–PO11 attainment &amp; 4-band distribution (0–100 scale)
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Measured zeros (0.0) are counted in the &lt;50 band;
                        unassessed or excluded students are reported separately
                        and never coerced to zero.
                      </p>
                    </div>

                    {/* Single-hue legend */}
                    <div
                      aria-label="4-band single-hue legend"
                      className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground"
                    >
                      {BUCKET_META.map((bucket) => (
                        <span
                          key={bucket.key}
                          className="inline-flex items-center gap-1.5"
                        >
                          <span
                            className={`size-2.5 rounded-[2px] ${bucket.swatchClass}`}
                            aria-hidden="true"
                          />
                          <span className="tabular-mono">{bucket.label}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  <PoAttainmentBarChart outcomes={analytics.outcomes} />
                </section>

                {/* 4-Band Distribution Summary Table */}
                <section
                  aria-labelledby="po-distribution-table-title"
                  className="space-y-2"
                >
                  <h3
                    id="po-distribution-table-title"
                    className="text-base font-semibold tracking-tight"
                  >
                    Cohort PO summary table
                  </h3>
                  <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                    <Table>
                      <TableCaption className="pb-3">
                        Published cohort PO attainment (0–100 scale), sample
                        size, coverage, and missing exclusions for Publication{' '}
                        {shortRef(analytics.publication_id)} (PO-Set v
                        {analytics.po_set_version}).
                      </TableCaption>
                      <TableHeader className="bg-[var(--surface-subtle)]">
                        <TableRow>
                          <TableHead scope="col">PO code</TableHead>
                          <TableHead scope="col" className="text-right">
                            Mean (0–100)
                          </TableHead>
                          <TableHead scope="col" className="text-right">
                            Median
                          </TableHead>
                          <TableHead scope="col" className="text-right">
                            Min–Max
                          </TableHead>
                          <TableHead scope="col" className="text-right">
                            Sample size (n / population)
                          </TableHead>
                          <TableHead scope="col" className="text-right">
                            Coverage (%)
                          </TableHead>
                          <TableHead scope="col">
                            Buckets (&lt;50 / 50–69.9 / 70–84.9 / 85–100)
                          </TableHead>
                          <TableHead scope="col">Missing / Excluded</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {analytics.outcomes.map((outcome) => {
                          const exclusionParts = formatExclusionParts(
                            outcome.exclusions,
                          );
                          return (
                            <TableRow
                              key={outcome.code}
                              className="transition-colors duration-150 hover:bg-[var(--surface-hover)]"
                            >
                              <th
                                scope="row"
                                className="p-2.5 text-left align-middle font-medium whitespace-nowrap"
                              >
                                <span className="tabular-mono">
                                  {outcome.code}
                                </span>
                                <span className="block max-w-[240px] truncate text-xs font-normal text-muted-foreground">
                                  {outcome.label}
                                </span>
                              </th>
                              <TableCell className="tabular-mono text-right">
                                {outcome.n === 0 || outcome.mean === null ? (
                                  <NotAssessedText />
                                ) : isMeasuredZero(outcome) ? (
                                  <MeasuredZeroTag value="0.0" />
                                ) : (
                                  outcome.mean
                                )}
                              </TableCell>
                              <TableCell className="tabular-mono text-right">
                                {outcome.n > 0 && outcome.median !== null
                                  ? outcome.median
                                  : '—'}
                              </TableCell>
                              <TableCell className="tabular-mono text-right">
                                {formatMinMax(outcome)}
                              </TableCell>
                              <TableCell className="tabular-mono text-right">
                                {outcome.n} / {outcome.population_size}
                              </TableCell>
                              <TableCell className="tabular-mono text-right">
                                {formatCoveragePercent(outcome.coverage)}
                              </TableCell>
                              <TableCell className="tabular-mono whitespace-nowrap">
                                {outcome.distribution['<50']} /{' '}
                                {outcome.distribution['50-69.9']} /{' '}
                                {outcome.distribution['70-84.9']} /{' '}
                                {outcome.distribution['85-100']}
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">
                                {exclusionParts.length > 0
                                  ? exclusionParts.join(', ')
                                  : 'None'}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </section>
              </>
            )}
          </div>
        )}

        {/* CHRONOLOGICAL TRENDS TAB PANEL */}
        {activeTab === 'trends' && activeProgramId && (
          <section
            id={trendsPanelId}
            role="tabpanel"
            aria-labelledby={trendsTabId}
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
                  Only publications sharing the same PO-set version can be
                  compared chronologically. Including a snapshot from a
                  different PO-set triggers the server compatibility guard.
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

            {/* Snapshot picker allowing selection of publications (including incompatible PO-Set v1) */}
            {publications.length > 0 && (
              <fieldset className="space-y-2 rounded-[var(--radius-card,10px)] border border-border/80 bg-[var(--surface-subtle)]/40 p-3.5">
                <legend className="px-1 text-xs font-medium text-muted-foreground">
                  Snapshots included in comparison
                </legend>
                <div className="flex flex-wrap gap-2">
                  {publications.map((pub) => {
                    const checked = selectedTrendPublicationIds.includes(pub.id);
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
                    comparison will be rejected by the server compatibility
                    guard.
                  </p>
                )}
              </fieldset>
            )}

            {trendsQuery.isPending && (
              <div className="space-y-3" role="status">
                <p className="text-sm text-muted-foreground">
                  Loading compatible PO-set trends…
                </p>
                <Skeleton className="h-52 w-full" />
              </div>
            )}

            {trendsQuery.isError && (
              <Alert variant="destructive">
                <AlertTitle>Trend comparison unavailable</AlertTitle>
                <AlertDescription>
                  {cohortErrorMessage(trendsQuery.error)}
                </AlertDescription>
              </Alert>
            )}

            {trendsQuery.data && (
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
                      PO-Set v{trendsQuery.data.po_set_version} ·{' '}
                      {trendsQuery.data.points.length} snapshot
                      {trendsQuery.data.points.length === 1 ? '' : 's'}
                    </Badge>
                  </div>
                )}

                {activeTrendPoCode && trendsQuery.data.points.length > 0 && (
                  <TrendAreaChart
                    points={trendsQuery.data.points}
                    selectedCode={activeTrendPoCode}
                  />
                )}

                <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                  <Table>
                    <TableCaption className="pb-3">
                      Trend comparison across compatible publications for PO-Set
                      v{trendsQuery.data.po_set_version}.
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
                      {trendsQuery.data.points.map((point) => (
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
          </section>
        )}
      </CardContent>
    </Card>
  );
}
