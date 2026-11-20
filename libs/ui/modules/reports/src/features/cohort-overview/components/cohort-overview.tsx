'use client';

import { useEffect, useId, useState } from 'react';
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
  NativeSelect,
  NativeSelectOption,
  Skeleton,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import { cohortErrorMessage, formatCoveragePercent, shortRef } from '../api';
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
  CoordinatorPublication,
} from '../types';

export interface CohortSelection {
  programId: string | null;
  publicationId: string | null;
}

export interface CohortOverviewProps {
  /** Authorized programs; fetched from /api/v1/programs/ when omitted. */
  programs?: CohortProgramOption[];
  /** Optional term filter options; fetched from /api/v1/terms/ when omitted. */
  terms?: CohortTermOption[];
  /** Optional course filter options; fetched from /api/v1/courses/ when omitted. */
  courses?: CohortCourseOption[];
  /** Initial program selection. */
  defaultProgramId?: string;
  /** Initial publication selection. */
  defaultPublicationId?: string;
  /** Whether to expand the compatible PO-set trend comparison by default. */
  defaultShowTrends?: boolean;
  /** Notified whenever the active program or publication changes. */
  onSelectionChange?: (selection: CohortSelection) => void;
}

const BUCKET_META: ReadonlyArray<{
  key: keyof CohortDistribution;
  label: string;
  barClass: string;
}> = [
  { key: '<50', label: '<50', barClass: 'bg-destructive/80' },
  { key: '50-69.9', label: '50–69.9', barClass: 'bg-amber-500/80' },
  { key: '70-84.9', label: '70–84.9', barClass: 'bg-sky-600/80' },
  { key: '85-100', label: '85–100', barClass: 'bg-emerald-600/80' },
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

function formatMean(outcome: CohortOutcomeMetric): string {
  if (outcome.n === 0 || outcome.mean === null) {
    return '— Not assessed';
  }
  return outcome.mean;
}

function formatMinMax(outcome: CohortOutcomeMetric): string {
  if (outcome.n === 0 || outcome.min === null || outcome.max === null) {
    return '—';
  }
  return `${outcome.min}–${outcome.max}`;
}

export function CohortOverview({
  programs: providedPrograms,
  terms: providedTerms,
  courses: providedCourses,
  defaultProgramId,
  defaultPublicationId,
  defaultShowTrends = false,
  onSelectionChange,
}: CohortOverviewProps) {
  const programSelectId = useId();
  const publicationSelectId = useId();
  const termSelectId = useId();
  const courseSelectId = useId();

  const programsQuery = useCoordinatorProgramsQuery(
    providedPrograms === undefined,
  );
  const termsQuery = useCohortTermsQuery(providedTerms === undefined);
  const coursesQuery = useCohortCoursesQuery(providedCourses === undefined);

  const programs = providedPrograms ?? programsQuery.data ?? [];
  const terms = providedTerms ?? termsQuery.data ?? [];
  const courses = providedCourses ?? coursesQuery.data ?? [];

  const [selectedProgramId, setSelectedProgramId] = useState<string>(
    defaultProgramId ?? '',
  );
  const [selectedPublicationId, setSelectedPublicationId] = useState<string>(
    defaultPublicationId ?? '',
  );
  const [selectedTermId, setSelectedTermId] = useState<string>('');
  const [selectedCourseId, setSelectedCourseId] = useState<string>('');
  const [showTrends, setShowTrends] = useState<boolean>(defaultShowTrends);

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

  const compatiblePublications =
    activePoSetVersion !== undefined
      ? publications.filter((p) => p.po_set_version === activePoSetVersion)
      : [];

  const trendsQuery = useCohortTrendsQuery(
    activeProgramId
      ? {
          programId: activeProgramId,
          poSetVersion: activePoSetVersion,
          publicationIds:
            compatiblePublications.length > 0
              ? compatiblePublications.map((p) => p.id)
              : undefined,
        }
      : null,
    showTrends && Boolean(activeProgramId),
  );

  useEffect(() => {
    onSelectionChange?.({
      programId: activeProgramId || null,
      publicationId: resolvedPublicationId,
    });
  }, [activeProgramId, resolvedPublicationId, onSelectionChange]);

  const isNotFound =
    analyticsQuery.isError &&
    analyticsQuery.error instanceof ApiError &&
    analyticsQuery.error.status === 404;

  const isFatalAnalyticsError = analyticsQuery.isError && !isNotFound;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>
              <h2>Cohort outcome overview</h2>
            </CardTitle>
            <CardDescription>
              Inspect published PO distributions, measurement coverage, and
              missing exclusions for your program cohort.
            </CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            aria-expanded={showTrends}
            disabled={!activeProgramId}
            onClick={() => setShowTrends((prev) => !prev)}
          >
            {showTrends ? 'Hide PO-set trends' : 'Compare PO-set trends'}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
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

        {programs.length === 0 && !programsQuery.isPending && !programsQuery.isError && (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>No published cohort analytics available</EmptyTitle>
              <EmptyDescription>
                No authorized programs were found for your coordinator scope.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}

        {programs.length > 0 && (
          <FieldGroup className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field>
              <FieldLabel htmlFor={programSelectId}>Program</FieldLabel>
              <NativeSelect
                id={programSelectId}
                value={activeProgramId}
                onChange={(event) => {
                  setSelectedProgramId(event.target.value);
                  setSelectedPublicationId('');
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
              <FieldLabel htmlFor={publicationSelectId}>
                Published snapshot
              </FieldLabel>
              <NativeSelect
                id={publicationSelectId}
                value={activePublicationId}
                disabled={publicationsQuery.isPending || publications.length === 0}
                onChange={(event) => setSelectedPublicationId(event.target.value)}
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
              <FieldLabel htmlFor={termSelectId}>Term</FieldLabel>
              <NativeSelect
                id={termSelectId}
                value={selectedTermId}
                onChange={(event) => setSelectedTermId(event.target.value)}
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
              <FieldLabel htmlFor={courseSelectId}>Course</FieldLabel>
              <NativeSelect
                id={courseSelectId}
                value={selectedCourseId}
                onChange={(event) => setSelectedCourseId(event.target.value)}
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
        )}

        {publicationsQuery.isError && (
          <Alert variant="destructive">
            <AlertTitle>Unable to load published snapshots</AlertTitle>
            <AlertDescription>
              {cohortErrorMessage(publicationsQuery.error)}
            </AlertDescription>
          </Alert>
        )}

        {activeProgramId && analyticsQuery.isPending && (
          <div className="space-y-3" role="status">
            <p className="text-sm text-muted-foreground">
              Loading cohort analytics…
            </p>
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-48 w-full" />
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
                <EmptyTitle>No published cohort analytics available</EmptyTitle>
                <EmptyDescription>
                  Publish a calculation run for this program to inspect cohort
                  distributions and coverage.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}

        {analytics && analytics.outcomes.length > 0 && (
          <>
            <section
              aria-label="Publication traceability metadata"
              className="space-y-3 rounded-lg border bg-muted/20 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    analytics.publication_status === 'stale'
                      ? 'destructive'
                      : 'default'
                  }
                >
                  {analytics.publication_status === 'stale'
                    ? 'Stale'
                    : 'Published'}
                </Badge>
                <Badge variant="outline" title={analytics.publication_id}>
                  Publication {shortRef(analytics.publication_id)}
                </Badge>
                <Badge variant="outline" title={analytics.run_id}>
                  Run {shortRef(analytics.run_id)}
                </Badge>
                <Badge variant="secondary">
                  PO-Set v{analytics.po_set_version}
                </Badge>
                <Badge variant="outline">
                  Policy {analytics.policy_version}
                </Badge>
                <Badge variant="outline">
                  n = {analytics.sample_size} / {analytics.population_size}
                </Badge>
                <Badge variant="outline">
                  {formatCoveragePercent(analytics.coverage)} coverage
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Publication ID: <code>{analytics.publication_id}</code> · Series
                v{analytics.series_version} · Total exclusions:{' '}
                {totalExclusionsCount(analytics.exclusions)} (
                {formatExclusionParts(analytics.exclusions).join(', ') ||
                  'None'}
                )
              </p>
              {analytics.publication_status === 'stale' && (
                <Alert variant="destructive">
                  <AlertTitle>Stale publication snapshot</AlertTitle>
                  <AlertDescription>
                    Underlying grades or syllabus mappings changed after this
                    snapshot was published. Values below remain immutable;
                    recalculate and publish a new snapshot to reflect updates.
                  </AlertDescription>
                </Alert>
              )}
            </section>

            <section aria-labelledby="po-distribution-chart-title" className="space-y-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h3
                    id="po-distribution-chart-title"
                    className="text-base font-semibold"
                  >
                    PO attainment distribution (0–100 scale)
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Measured zeros (0.0) are counted in the &lt;50 bucket;
                    unassessed or excluded students are reported separately and
                    never coerced to zero.
                  </p>
                </div>
                <div
                  aria-label="Score scale 0 to 100"
                  className="flex items-center gap-3 text-xs font-medium text-muted-foreground"
                >
                  <span>0</span>
                  <span>50</span>
                  <span>70</span>
                  <span>85</span>
                  <span>100</span>
                </div>
              </div>

              <div className="space-y-3">
                {analytics.outcomes.map((outcome) => {
                  const exclusionParts = formatExclusionParts(
                    outcome.exclusions,
                  );
                  const coveragePct = formatCoveragePercent(outcome.coverage);
                  return (
                    <div
                      key={outcome.code}
                      className="space-y-2 rounded-md border p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <div>
                          <span className="font-semibold">{outcome.code}</span>{' '}
                          <span className="text-sm text-muted-foreground">
                            {outcome.label}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-medium">
                            Mean: {formatMean(outcome)}
                          </span>
                          <span className="text-muted-foreground">
                            n = {outcome.n} ({outcome.n} /{' '}
                            {outcome.population_size})
                          </span>
                          <span className="text-muted-foreground">
                            Coverage: {coveragePct}
                          </span>
                        </div>
                      </div>

                      {outcome.n > 0 ? (
                        <div className="space-y-1.5">
                          <div
                            className="flex h-4 w-full overflow-hidden rounded bg-muted"
                            role="img"
                            aria-label={`${outcome.code} distribution across ${outcome.n} measured students on a 0–100 scale: <50: ${outcome.distribution['<50']}, 50–69.9: ${outcome.distribution['50-69.9']}, 70–84.9: ${outcome.distribution['70-84.9']}, 85–100: ${outcome.distribution['85-100']}`}
                          >
                            {BUCKET_META.map((bucket) => {
                              const count = outcome.distribution[bucket.key];
                              if (count === 0) return null;
                              const widthPct = (count / outcome.n) * 100;
                              return (
                                <div
                                  key={bucket.key}
                                  className={bucket.barClass}
                                  style={{ width: `${widthPct}%` }}
                                  title={`${bucket.label}: ${count}`}
                                />
                              );
                            })}
                          </div>
                          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                            {BUCKET_META.map((bucket) => (
                              <span key={bucket.key}>
                                {bucket.label}:{' '}
                                <strong className="text-foreground">
                                  {outcome.distribution[bucket.key]}
                                </strong>
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs italic text-muted-foreground">
                          — Not assessed (no measured scores; 0 /{' '}
                          {outcome.population_size} measured)
                        </p>
                      )}

                      {exclusionParts.length > 0 && (
                        <p className="text-xs text-muted-foreground">
                          Missing / excluded: {exclusionParts.join(' · ')}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            <section aria-labelledby="po-distribution-table-title" className="space-y-2">
              <h3
                id="po-distribution-table-title"
                className="text-base font-semibold"
              >
                Cohort PO summary table
              </h3>
              <Table>
                <TableCaption>
                  Published cohort PO attainment (0–100 scale), sample size,
                  coverage, and missing exclusions for Publication{' '}
                  {shortRef(analytics.publication_id)} (PO-Set v
                  {analytics.po_set_version}).
                </TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">PO Code</TableHead>
                    <TableHead scope="col">Mean (0–100)</TableHead>
                    <TableHead scope="col">Median</TableHead>
                    <TableHead scope="col">Min–Max</TableHead>
                    <TableHead scope="col">
                      Sample size (n / population)
                    </TableHead>
                    <TableHead scope="col">Coverage (%)</TableHead>
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
                      <TableRow key={outcome.code}>
                        <th
                          scope="row"
                          className="p-2 text-left align-middle font-medium whitespace-nowrap"
                        >
                          {outcome.code}
                          <span className="block text-xs font-normal text-muted-foreground">
                            {outcome.label}
                          </span>
                        </th>
                        <TableCell>{formatMean(outcome)}</TableCell>
                        <TableCell>
                          {outcome.n > 0 && outcome.median !== null
                            ? outcome.median
                            : '—'}
                        </TableCell>
                        <TableCell>{formatMinMax(outcome)}</TableCell>
                        <TableCell>
                          {outcome.n} / {outcome.population_size}
                        </TableCell>
                        <TableCell>
                          {formatCoveragePercent(outcome.coverage)}
                        </TableCell>
                        <TableCell>
                          {outcome.distribution['<50']} /{' '}
                          {outcome.distribution['50-69.9']} /{' '}
                          {outcome.distribution['70-84.9']} /{' '}
                          {outcome.distribution['85-100']}
                        </TableCell>
                        <TableCell>
                          {exclusionParts.length > 0
                            ? exclusionParts.join(', ')
                            : 'None'}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </section>
          </>
        )}

        {showTrends && activeProgramId && (
          <section
            aria-labelledby="po-trends-title"
            className="space-y-3 border-t pt-4"
          >
            <div>
              <h3 id="po-trends-title" className="text-base font-semibold">
                Compatible PO-set trend comparison
              </h3>
              <p className="text-xs text-muted-foreground">
                Only publications sharing the same PO-set version are compared
                so changed PO definitions are never blended into a trend.
              </p>
            </div>

            {trendsQuery.isPending && (
              <p role="status" className="text-sm text-muted-foreground">
                Loading compatible PO-set trends…
              </p>
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
              <Table>
                <TableCaption>
                  Trend comparison across compatible publications for PO-Set v
                  {trendsQuery.data.po_set_version}.
                </TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Snapshot</TableHead>
                    <TableHead scope="col">PO-Set</TableHead>
                    <TableHead scope="col">Status</TableHead>
                    <TableHead scope="col">Sample (n / population)</TableHead>
                    <TableHead scope="col">Coverage</TableHead>
                    <TableHead scope="col">PO means</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {trendsQuery.data.points.map((point) => (
                    <TableRow key={point.publication_id}>
                      <th
                        scope="row"
                        className="p-2 text-left align-middle font-medium whitespace-nowrap"
                      >
                        {point.term?.label ?? shortRef(point.publication_id)}
                        <span className="block text-xs font-normal text-muted-foreground">
                          Pub {shortRef(point.publication_id)} · Series v
                          {point.series_version}
                        </span>
                      </th>
                      <TableCell>v{point.po_set_version}</TableCell>
                      <TableCell>
                        {point.publication_status === 'stale'
                          ? 'Stale'
                          : 'Published'}
                      </TableCell>
                      <TableCell>
                        {point.sample_size} / {point.population_size}
                      </TableCell>
                      <TableCell>
                        {formatCoveragePercent(point.coverage)}
                      </TableCell>
                      <TableCell>
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
            )}
          </section>
        )}
      </CardContent>
    </Card>
  );
}
