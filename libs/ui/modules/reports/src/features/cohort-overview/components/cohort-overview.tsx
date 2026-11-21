'use client';

import { useCallback, useEffect, useId, useState } from 'react';
import { ApiError } from '@outcometrik/api';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Skeleton,
} from '@outcometrik/ui';
import { cohortErrorMessage } from '../api';
import {
  useCohortAnalyticsQuery,
  useCohortCoursesQuery,
  useCohortTermsQuery,
  useCoordinatorProgramsQuery,
  useCoordinatorPublicationsQuery,
} from '../hooks/use-cohort-overview';
import type {
  CohortCourseOption,
  CohortProgramOption,
  CohortTermOption,
} from '../types';
import { CohortFilterBar } from './cohort-filter-bar';
import {
  BUCKET_META,
  formatExclusionParts,
  totalExclusionsCount,
} from './cohort-formatters';
import { CohortSummaryTable } from './cohort-summary-table';
import { CohortTraceabilityHeader } from './cohort-traceability-header';
import { CohortTrendsPanel } from './cohort-trends-panel';
import { PoAttainmentBarChart } from './po-attainment-chart';

export { BUCKET_META, formatExclusionParts, totalExclusionsCount };

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

  const selectedProgramId = controlledProgramId ?? internalProgramId;
  const selectedPublicationId = controlledPublicationId ?? internalPublicationId;
  const selectedTermId = controlledTermId ?? internalTermId;
  const selectedCourseId = controlledCourseId ?? internalCourseId;
  const activeTab: CohortOverviewTab = controlledTab ?? internalTab;

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

  const updateFilters = useCallback(
    (patch: Partial<CohortFilterValues>) => {
      const next: CohortFilterValues = {
        programId: patch.programId ?? activeProgramId,
        publicationId:
          patch.publicationId !== undefined
            ? patch.publicationId
            : selectedPublicationId,
        termId: patch.termId !== undefined ? patch.termId : selectedTermId,
        courseId:
          patch.courseId !== undefined ? patch.courseId : selectedCourseId,
      };
      if (controlledProgramId === undefined)
        setInternalProgramId(next.programId);
      if (controlledPublicationId === undefined)
        setInternalPublicationId(next.publicationId);
      if (controlledTermId === undefined) setInternalTermId(next.termId);
      if (controlledCourseId === undefined) setInternalCourseId(next.courseId);
      onFiltersChange?.(next);
    },
    [
      activeProgramId,
      selectedPublicationId,
      selectedTermId,
      selectedCourseId,
      controlledProgramId,
      controlledPublicationId,
      controlledTermId,
      controlledCourseId,
      onFiltersChange,
    ],
  );

  const handleProgramChange = useCallback(
    (nextProgramId: string) =>
      updateFilters({ programId: nextProgramId, publicationId: '' }),
    [updateFilters],
  );
  const handlePublicationChange = useCallback(
    (nextPubId: string) => updateFilters({ publicationId: nextPubId }),
    [updateFilters],
  );
  const handleTermChange = useCallback(
    (nextTermId: string) => updateFilters({ termId: nextTermId }),
    [updateFilters],
  );
  const handleCourseChange = useCallback(
    (nextCourseId: string) => updateFilters({ courseId: nextCourseId }),
    [updateFilters],
  );
  const handleResetFilters = useCallback(
    () => updateFilters({ publicationId: '', termId: '', courseId: '' }),
    [updateFilters],
  );

  const handleTabChange = useCallback(
    (nextTab: CohortOverviewTab) => {
      if (controlledTab === undefined) setInternalTab(nextTab);
      onTabChange?.(nextTab);
    },
    [controlledTab, onTabChange],
  );

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
        {providedPrograms === undefined && programsQuery.isPending ? (
          <div className="space-y-2" role="status">
            <p className="text-sm text-muted-foreground">
              Loading authorized programs…
            </p>
            <Skeleton className="h-10 w-full" />
          </div>
        ) : null}

        {providedPrograms === undefined && programsQuery.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Unable to load programs</AlertTitle>
            <AlertDescription>
              {cohortErrorMessage(programsQuery.error)}
            </AlertDescription>
          </Alert>
        ) : null}

        {programs.length === 0 &&
        !programsQuery.isPending &&
        !programsQuery.isError ? (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>No published cohort analytics available</EmptyTitle>
              <EmptyDescription>
                No authorized programs were found for your coordinator scope.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}

        {programs.length > 0 ? (
          <CohortFilterBar
            programs={programs}
            publications={publications}
            publicationsPending={publicationsQuery.isPending}
            terms={terms}
            courses={courses}
            activeProgramId={activeProgramId}
            activePublicationId={activePublicationId}
            selectedTermId={selectedTermId}
            selectedCourseId={selectedCourseId}
            hasActiveFilters={hasActiveFilters}
            onProgramChange={handleProgramChange}
            onPublicationChange={handlePublicationChange}
            onTermChange={handleTermChange}
            onCourseChange={handleCourseChange}
            onResetFilters={handleResetFilters}
          />
        ) : null}

        {publicationsQuery.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Unable to load published snapshots</AlertTitle>
            <AlertDescription>
              {cohortErrorMessage(publicationsQuery.error)}
            </AlertDescription>
          </Alert>
        ) : null}

        {activeTab === 'overview' ? (
          <div
            id={overviewPanelId}
            role="tabpanel"
            aria-labelledby={overviewTabId}
            className="space-y-6"
          >
            {activeProgramId && analyticsQuery.isPending ? (
              <div className="space-y-3" role="status">
                <p className="text-sm text-muted-foreground">
                  Loading cohort analytics…
                </p>
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-56 w-full" />
              </div>
            ) : null}

            {isFatalAnalyticsError ? (
              <Alert variant="destructive">
                <AlertTitle>Unable to load cohort analytics</AlertTitle>
                <AlertDescription>
                  {cohortErrorMessage(analyticsQuery.error)}
                </AlertDescription>
              </Alert>
            ) : null}

            {activeProgramId &&
            !analyticsQuery.isPending &&
            (isNotFound || (analytics && analytics.outcomes.length === 0)) ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>
                    No published cohort analytics available
                  </EmptyTitle>
                  <EmptyDescription>
                    Publish a calculation run for this program to inspect cohort
                    distributions and coverage.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : null}

            {analytics && analytics.outcomes.length > 0 ? (
              <>
                <CohortTraceabilityHeader analytics={analytics} />

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
                        PO1–PO11 attainment &amp; 4-band distribution (0–100
                        scale)
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Measured zeros (0.0) are counted in the &lt;50 band;
                        unassessed or excluded students are reported separately
                        and never coerced to zero.
                      </p>
                    </div>

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

                <CohortSummaryTable
                  publicationId={analytics.publication_id}
                  poSetVersion={analytics.po_set_version}
                  outcomes={analytics.outcomes}
                />
              </>
            ) : null}
          </div>
        ) : null}

        {activeTab === 'trends' && activeProgramId ? (
          <CohortTrendsPanel
            key={activeProgramId}
            panelId={trendsPanelId}
            tabId={trendsTabId}
            programId={activeProgramId}
            publications={publications}
            activePoSetVersion={activePoSetVersion}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
