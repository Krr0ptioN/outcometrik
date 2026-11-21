'use client';

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { ApiError } from '@outcometrik/api';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Skeleton,
  createQueryState,
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
  CohortAnalyticsResponse,
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
import { CohortHeroStrip } from './cohort-hero-strip';
import {
  CohortOverviewProvider,
  type CohortOverviewContextValue,
} from './cohort-overview-context';
import { CohortSummaryTable } from './cohort-summary-table';
import { CohortTrendsPanel } from './cohort-trends-panel';
import { PoAttainmentBarChart } from './po-attainment-chart';

export { BUCKET_META, formatExclusionParts, totalExclusionsCount };

const CohortQuery = createQueryState({ formatError: cohortErrorMessage });
const isNotFoundApiError = (error: unknown) =>
  error instanceof ApiError && error.status === 404;

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

export interface CohortOverviewDefaults {
  /** Initial program selection (uncontrolled mode). */
  defaultProgramId?: string;
  /** Initial publication selection (uncontrolled mode). */
  defaultPublicationId?: string;
  /** Initial term filter (uncontrolled mode). */
  defaultTermId?: string;
  /** Initial course filter (uncontrolled mode). */
  defaultCourseId?: string;
  /** Whether to open the Chronological Trends tab by default. */
  defaultShowTrends?: boolean;
}

export interface CohortOverviewProps extends CohortOverviewDefaults {
  /** Authorized programs; fetched from /api/v1/programs/ when omitted. */
  programs?: CohortProgramOption[];
  /** Optional term filter options; fetched from /api/v1/terms/ when omitted. */
  terms?: CohortTermOption[];
  /** Optional course filter options; fetched from /api/v1/courses/ when omitted. */
  courses?: CohortCourseOption[];
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
  /** Notified whenever any filter value changes (for URL query synchronization). */
  onFiltersChange?: (filters: CohortFilterValues) => void;
  /** Notified whenever the active tab changes. */
  onTabChange?: (tab: CohortOverviewTab) => void;
  /** Optional right-rail content (e.g. ExportPanel) placed beside the main analytics canvas on wide screens. */
  sidebarSlot?: ReactNode;
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
  sidebarSlot,
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

  const contextValue = useMemo<CohortOverviewContextValue>(
    () => ({
      programs,
      publications,
      publicationsPending: publicationsQuery.isPending,
      terms,
      courses,
      activeProgramId,
      activePublicationId,
      selectedTermId,
      selectedCourseId,
      activePoSetVersion,
      hasActiveFilters,
      onProgramChange: handleProgramChange,
      onPublicationChange: handlePublicationChange,
      onTermChange: handleTermChange,
      onCourseChange: handleCourseChange,
      onResetFilters: handleResetFilters,
    }),
    [
      programs,
      publications,
      publicationsQuery.isPending,
      terms,
      courses,
      activeProgramId,
      activePublicationId,
      selectedTermId,
      selectedCourseId,
      activePoSetVersion,
      hasActiveFilters,
      handleProgramChange,
      handlePublicationChange,
      handleTermChange,
      handleCourseChange,
      handleResetFilters,
    ],
  );

  return (
    <CohortOverviewProvider value={contextValue}>
      <div className="space-y-6">
        {/* Top Command Bar: Title + Segmented View Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/80 pb-4">
          <div className="space-y-0.5">
            <h2 className="text-base font-semibold tracking-tight text-foreground">
              Cohort outcome overview
            </h2>
            <p className="text-xs text-muted-foreground">
              Published PO1–PO11 attainment, 4-band distributions, measurement
              coverage, and PO-set-safe chronological trends.
            </p>
          </div>

          <div
            role="tablist"
            aria-label="Cohort analytics views"
            className="inline-flex items-center rounded-[var(--radius-input,6px)] border border-border bg-[var(--surface-subtle)]/70 p-0.5"
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

        {/* URL-Synced Filter Bar */}
        <CohortQuery
          query={programsQuery}
          fallbackData={providedPrograms}
          isEmpty={(list) => list.length === 0}
        >
          <CohortQuery.Loading>
            <div className="space-y-2" role="status">
              <p className="text-sm text-muted-foreground">
                Loading authorized programs…
              </p>
              <Skeleton className="h-10 w-full" />
            </div>
          </CohortQuery.Loading>
          <CohortQuery.Error title="Unable to load programs" />
          <CohortQuery.Empty>
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No published cohort analytics available</EmptyTitle>
                <EmptyDescription>
                  No authorized programs were found for your coordinator scope.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CohortQuery.Empty>
          <CohortQuery.Ready>
            <CohortFilterBar />
          </CohortQuery.Ready>
        </CohortQuery>

        <CohortQuery query={publicationsQuery}>
          <CohortQuery.Error title="Unable to load published snapshots" />
        </CohortQuery>

        {/* Primary Asymmetric Analytics Workspace */}
        <div
          className={
            sidebarSlot
              ? 'grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]'
              : 'space-y-6'
          }
        >
          <div className="min-w-0 space-y-6">
            {activeTab === 'overview' && activeProgramId && (
              <div
                id={overviewPanelId}
                role="tabpanel"
                aria-labelledby={overviewTabId}
                className="space-y-6"
              >
                <CohortQuery
                  query={analyticsQuery}
                  isEmpty={(data) => data.outcomes.length === 0}
                  treatErrorAsEmpty={isNotFoundApiError}
                >
                  <CohortQuery.Loading>
                    <div className="space-y-4" role="status">
                      <p className="text-sm text-muted-foreground">
                        Loading cohort analytics…
                      </p>
                      <div className="grid gap-4 lg:grid-cols-12">
                        <Skeleton className="h-28 lg:col-span-5" />
                        <Skeleton className="h-28 lg:col-span-3" />
                        <Skeleton className="h-28 lg:col-span-4" />
                      </div>
                      <Skeleton className="h-72 w-full" />
                    </div>
                  </CohortQuery.Loading>
                  <CohortQuery.Error title="Unable to load cohort analytics" />
                  <CohortQuery.Empty>
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
                  </CohortQuery.Empty>
                  <CohortQuery.Ready>
                    {(data: CohortAnalyticsResponse) => (
                      <>
                        <CohortHeroStrip analytics={data} />

                        <section
                          aria-labelledby="po-distribution-chart-title"
                          className="space-y-3"
                        >
                          <div className="flex flex-wrap items-end justify-between gap-3">
                            <div>
                              <h3
                                id="po-distribution-chart-title"
                                className="text-base font-semibold tracking-tight"
                              >
                                PO1–PO11 attainment &amp; 4-band distribution
                                (0–100 scale)
                              </h3>
                              <p className="text-xs text-muted-foreground">
                                Measured zeros (0.0) are counted in the &lt;50
                                band; unassessed or excluded students are
                                reported separately and never coerced to zero.
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
                                  <span className="tabular-mono">
                                    {bucket.label}
                                  </span>
                                </span>
                              ))}
                            </div>
                          </div>

                          <PoAttainmentBarChart outcomes={data.outcomes} />
                        </section>

                        <CohortSummaryTable
                          publicationId={data.publication_id}
                          poSetVersion={data.po_set_version}
                          outcomes={data.outcomes}
                        />
                      </>
                    )}
                  </CohortQuery.Ready>
                </CohortQuery>
              </div>
            )}

            {activeTab === 'trends' && activeProgramId && (
              <CohortTrendsPanel
                key={activeProgramId}
                panelId={trendsPanelId}
                tabId={trendsTabId}
              />
            )}
          </div>

          {sidebarSlot && (
            <aside
              aria-label="Exports and governance actions"
              className="space-y-4 xl:sticky xl:top-6"
            >
              {sidebarSlot}
            </aside>
          )}
        </div>
      </div>
    </CohortOverviewProvider>
  );
}
