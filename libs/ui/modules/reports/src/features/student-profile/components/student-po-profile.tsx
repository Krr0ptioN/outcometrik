'use client';

import type { ReactNode } from 'react';
import { Fragment, useEffect, useId, useMemo, useState } from 'react';
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
  FieldDescription,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
  Separator,
  Skeleton,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import {
  useStudentPublicationScores,
  useStudentPublications,
} from '../hooks/use-student-profile';
import {
  buildStudentPOProfile,
  roundHalfUpOneDecimal,
  studentProfileErrorMessage,
} from '../profile';
import type {
  AssessmentEvidenceContribution,
  LoEvidenceContribution,
  OutcomeScoreStatus,
  StudentPOProfileItem,
  StudentPublication,
} from '../types';

export interface StudentPOProfileProps {
  /** Optional slot receiving the active publication ID (e.g. for wiring ExportPanel). */
  renderActions?: (publicationId: string | null) => ReactNode;
  /** Optional callback notified whenever the selected publication changes. */
  onSelectedPublicationChange?: (publicationId: string | null) => void;
  /** Optional initial expanded PO code (useful for deep links or deterministic tests). */
  initialExpandedCode?: string | null;
}

const SCALE_TICKS = [0, 25, 50, 75, 100] as const;

function shortRef(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function formatPublishedTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

function formatSnapshotOptionLabel(pub: StudentPublication): string {
  const scope =
    pub.scope_kind === 'offering'
      ? (pub.offering_label ?? 'Course offering')
      : `${pub.program_code ?? 'Program'} cumulative`;
  const term = pub.term_label ? ` · ${pub.term_label}` : '';
  const staleTag = pub.stale ? ' (Stale)' : '';
  return `v${pub.series_version} · ${scope}${term} · ${formatPublishedTimestamp(pub.published_at)}${staleTag}`;
}

function statusBadgeVariant(
  status: OutcomeScoreStatus,
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'OK') return 'default';
  if (status === 'INCOMPLETE') return 'destructive';
  if (status === 'ALL_EXEMPT') return 'secondary';
  return 'outline';
}

function formatNumericOrDash(raw: string | null | undefined): string {
  if (raw === null || raw === undefined || raw.trim() === '') return '—';
  return roundHalfUpOneDecimal(raw);
}

function AssessmentBreakdownList({
  assessments,
}: {
  assessments: AssessmentEvidenceContribution[];
}) {
  if (assessments.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No assessment contributions recorded for this learning outcome.
      </p>
    );
  }
  return (
    <ul className="mt-2 space-y-1.5 border-l-2 border-border pl-3 text-xs">
      {assessments.map((asmt, idx) => (
        <li
          key={`${asmt.assessment_code}-${idx}`}
          className="flex flex-wrap items-center justify-between gap-2"
        >
          <div>
            <span className="font-medium">{asmt.assessment_code}</span>
            <span className="ml-2 text-muted-foreground">
              Weight: {asmt.weight}
            </span>
            {asmt.grade_version !== null && (
              <span className="ml-2 text-muted-foreground">
                Grade v{asmt.grade_version}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {asmt.points_earned !== null && asmt.points_possible !== null ? (
              <span>
                Raw: {asmt.points_earned}/{asmt.points_possible}
              </span>
            ) : (
              <span>State: {asmt.grade_state}</span>
            )}
            {asmt.normalized_score !== null && (
              <Badge variant="outline">
                Normalized: {formatNumericOrDash(asmt.normalized_score)} / 100
              </Badge>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function LoBreakdownList({
  learningOutcomes,
}: {
  learningOutcomes: LoEvidenceContribution[];
}) {
  if (learningOutcomes.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No learning outcome breakdown recorded in this snapshot.
      </p>
    );
  }
  return (
    <div className="mt-2 space-y-2 border-l-2 border-border pl-3">
      {learningOutcomes.map((lo, idx) => (
        <div
          key={`${lo.lo_code}-${lo.learning_outcome_id ?? idx}`}
          className="rounded-md border bg-background p-2.5 text-xs"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="font-medium">
              {lo.lo_code}
              <span className="ml-2 font-normal text-muted-foreground">
                LO→PO weight: {lo.weight}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span>Score: {formatNumericOrDash(lo.value)}</span>
              {lo.numerator && lo.denominator && (
                <span className="text-muted-foreground">
                  ({lo.numerator} / {lo.denominator})
                </span>
              )}
            </div>
          </div>
          <AssessmentBreakdownList assessments={lo.assessment_contributions} />
        </div>
      ))}
    </div>
  );
}

function EvidenceDrillDown({
  item,
  publication,
}: {
  item: StudentPOProfileItem;
  publication: StudentPublication;
}) {
  const hasCourses = item.courses.length > 0;
  const hasLos = item.learningOutcomes.length > 0;

  return (
    <div className="space-y-4 rounded-md bg-muted/30 p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold">
            {item.code}
            {item.label ? ` — ${item.label}` : ''} evidence trace
          </h4>
          {item.description && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {item.description}
            </p>
          )}
        </div>
        <Badge variant={statusBadgeVariant(item.status)}>
          {item.statusLabel}
        </Badge>
      </div>

      <dl className="grid gap-3 rounded-md border bg-background p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">Formula</dt>
          <dd className="mt-0.5 font-mono font-medium">{item.formula}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Numerator / Denominator</dt>
          <dd className="mt-0.5 font-mono font-medium">
            {item.numerator !== null && item.denominator !== null
              ? `${item.numerator} / ${item.denominator}`
              : '— (no positive denominator)'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Display score &amp; coverage</dt>
          <dd className="mt-0.5 font-medium">
            {item.displayValue} / 100 · Coverage {item.coverageDisplay}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Source revisions</dt>
          <dd className="mt-0.5 font-medium">
            {[
              `PO set v${publication.po_set_version}`,
              `Publication v${publication.series_version}`,
              ...item.sourceRevisions,
            ].join(' · ')}
          </dd>
        </div>
      </dl>

      {hasCourses && (
        <div className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Course contributions (1–5 relevance weights) → Learning Outcomes →
            Assessments
          </h5>
          <div className="space-y-3">
            {item.courses.map((course, idx) => (
              <div
                key={`${course.course_code}-${course.offering_id}-${idx}`}
                className="rounded-md border bg-background p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div>
                    <span className="font-semibold">{course.course_code}</span>
                    {course.term && (
                      <span className="ml-2 text-muted-foreground">
                        {course.term}
                      </span>
                    )}
                    <span className="ml-2 text-muted-foreground">
                      Course→PO weight: {course.weight}
                    </span>
                    {course.syllabus_version !== null && (
                      <span className="ml-2 text-muted-foreground">
                        Syllabus v{course.syllabus_version}
                      </span>
                    )}
                    {course.attempt_number !== null && (
                      <span className="ml-2 text-muted-foreground">
                        Attempt #{course.attempt_number}
                      </span>
                    )}
                  </div>
                  <Badge variant="outline">
                    Course PO:{' '}
                    {formatNumericOrDash(course.value ?? course.course_po_value)}
                  </Badge>
                </div>
                <LoBreakdownList learningOutcomes={course.lo_contributions} />
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasCourses && hasLos && (
        <div className="space-y-2">
          <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Learning Outcomes (1–5 weights) → Assessments → Normalized grades
          </h5>
          <LoBreakdownList learningOutcomes={item.learningOutcomes} />
        </div>
      )}

      {!hasCourses && !hasLos && (
        <p className="text-xs text-muted-foreground">
          No contributing courses or assessments were mapped to {item.code} in
          this published snapshot. Unassessed outcomes are shown as &ldquo;—&rdquo;
          rather than 0.
        </p>
      )}

      {item.missing.length > 0 && (
        <p className="text-xs text-destructive">
          Missing inputs: {item.missing.join(', ')}
        </p>
      )}

      {item.exemptions.length > 0 && (
        <div className="text-xs text-muted-foreground">
          <span className="font-medium">Exemptions excluded from denominator:</span>{' '}
          {item.exemptions.map((ex) => `${ex.label} (${ex.reason})`).join(', ')}
        </div>
      )}
    </div>
  );
}

export function StudentPOProfile({
  renderActions,
  onSelectedPublicationChange,
  initialExpandedCode = null,
}: StudentPOProfileProps) {
  const selectId = useId();
  const sectionHeadingId = useId();
  const publicationsQuery = useStudentPublications();
  const publications = publicationsQuery.data ?? [];

  const [selectedId, setSelectedId] = useState<string>('');
  const [expandedCode, setExpandedCode] = useState<string | null>(
    initialExpandedCode,
  );

  const activePublication: StudentPublication | null = useMemo(() => {
    if (publications.length === 0) return null;
    return (
      publications.find((pub) => pub.id === selectedId) ?? publications[0]
    );
  }, [publications, selectedId]);

  const activePublicationId = activePublication?.id ?? null;

  useEffect(() => {
    onSelectedPublicationChange?.(activePublicationId);
  }, [activePublicationId, onSelectedPublicationChange]);

  const scoresQuery = useStudentPublicationScores(activePublicationId);

  const profileItems = useMemo(() => {
    if (!activePublication || !scoresQuery.data) return [];
    return buildStudentPOProfile(
      scoresQuery.data,
      activePublication.program_outcomes,
    );
  }, [activePublication, scoresQuery.data]);

  const measuredCount = profileItems.filter(
    (item) => item.value !== null,
  ).length;

  if (publicationsQuery.isPending) {
    return (
      <section aria-labelledby={sectionHeadingId} className="space-y-4">
        <Card role="status" aria-live="polite">
          <CardHeader>
            <CardTitle>
              <h2 id={sectionHeadingId}>Program Outcome profile (PO1–PO11)</h2>
            </CardTitle>
            <CardDescription>
              Loading published outcome snapshots…
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full" />
          </CardContent>
        </Card>
      </section>
    );
  }

  if (publicationsQuery.isError) {
    return (
      <section aria-labelledby={sectionHeadingId} className="space-y-4">
        <h2 id={sectionHeadingId} className="text-xl font-semibold">
          Program Outcome profile (PO1–PO11)
        </h2>
        <Alert variant="destructive" role="alert">
          <AlertTitle>Unable to load published outcome profile</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{studentProfileErrorMessage(publicationsQuery.error)}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void publicationsQuery.refetch()}
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      </section>
    );
  }

  if (!activePublication) {
    return (
      <section aria-labelledby={sectionHeadingId} className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>
              <h2 id={sectionHeadingId}>Program Outcome profile (PO1–PO11)</h2>
            </CardTitle>
            <CardDescription>
              Published, traceable attainment across all eleven program outcomes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No published outcome snapshots yet</EmptyTitle>
                <EmptyDescription>
                  Your PO1–PO11 profile and evidence breakdown will appear here
                  once your program publishes an official student snapshot.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CardContent>
        </Card>
        {renderActions?.(null)}
      </section>
    );
  }

  return (
    <section aria-labelledby={sectionHeadingId} className="space-y-6">
      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>
                <h2 id={sectionHeadingId}>Program Outcome profile (PO1–PO11)</h2>
              </CardTitle>
              <CardDescription>
                Immutable published attainment across all 11 program outcomes.
                Unassessed outcomes appear as &ldquo;Not assessed&rdquo; (—),
                never zero.
              </CardDescription>
            </div>
            <Badge
              variant={activePublication.stale ? 'destructive' : 'default'}
            >
              {activePublication.stale
                ? 'Stale — source grades/mappings changed since publication; historical snapshot preserved'
                : 'Current'}
            </Badge>
          </div>

          <Field>
            <FieldLabel htmlFor={selectId}>Published snapshot</FieldLabel>
            <NativeSelect
              id={selectId}
              value={activePublication.id}
              onChange={(event) => {
                setSelectedId(event.target.value);
                setExpandedCode(null);
              }}
            >
              {publications.map((pub) => (
                <NativeSelectOption key={pub.id} value={pub.id}>
                  {formatSnapshotOptionLabel(pub)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <FieldDescription>
              Switch between your historical published snapshots without
              altering immutable records.
            </FieldDescription>
          </Field>

          <dl className="grid gap-3 rounded-md border bg-muted/20 p-3 text-xs sm:grid-cols-2 lg:grid-cols-6">
            <div>
              <dt className="text-muted-foreground">Publication</dt>
              <dd
                className="mt-0.5 font-mono font-medium"
                title={activePublication.id}
              >
                {shortRef(activePublication.id)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Run</dt>
              <dd
                className="mt-0.5 font-mono font-medium"
                title={activePublication.run}
              >
                {shortRef(activePublication.run)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">PO-set version</dt>
              <dd className="mt-0.5 font-medium">
                v{activePublication.po_set_version}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Series version</dt>
              <dd className="mt-0.5 font-medium">
                v{activePublication.series_version}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Published at</dt>
              <dd className="mt-0.5 font-medium">
                {formatPublishedTimestamp(activePublication.published_at)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Measured POs</dt>
              <dd className="mt-0.5 font-medium">
                {scoresQuery.data ? `${measuredCount} / ${profileItems.length}` : '—'}
              </dd>
            </div>
          </dl>

          {activePublication.stale && (
            <Alert variant="destructive" role="status">
              <AlertTitle>Historical snapshot is stale</AlertTitle>
              <AlertDescription>
                Source grades or syllabus mappings changed after this snapshot
                was published. Historical scores and evidence below remain
                unchanged until a new snapshot is published.
              </AlertDescription>
            </Alert>
          )}
        </CardHeader>

        <CardContent className="space-y-6">
          {scoresQuery.isPending && (
            <div role="status" aria-live="polite" className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Loading published PO1–PO11 scores…
              </p>
              <Skeleton className="h-48 w-full" />
            </div>
          )}

          {scoresQuery.isError && (
            <Alert variant="destructive" role="alert">
              <AlertTitle>Unable to load snapshot scores</AlertTitle>
              <AlertDescription className="space-y-3">
                <p>{studentProfileErrorMessage(scoresQuery.error)}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void scoresQuery.refetch()}
                >
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {scoresQuery.data && (
            <>
              <div
                aria-label="Program Outcome attainment chart (0 to 100 scale)"
                className="space-y-3"
              >
                <div className="flex items-center justify-between gap-4 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">
                    PO1–PO11 Attainment Overview (0–100 scale)
                  </span>
                  <span>
                    {measuredCount} of {profileItems.length} outcomes measured
                  </span>
                </div>

                <div
                  aria-hidden="true"
                  className="grid grid-cols-[6rem_1fr_9rem] items-center gap-3 text-[11px] text-muted-foreground"
                >
                  <span>Outcome</span>
                  <div className="flex justify-between border-b pb-1 font-mono">
                    {SCALE_TICKS.map((tick) => (
                      <span key={tick}>{tick}</span>
                    ))}
                  </div>
                  <span className="text-right">Score · Status</span>
                </div>

                <ul className="space-y-2">
                  {profileItems.map((item) => {
                    const isMeasured = item.value !== null;
                    const barWidth = isMeasured
                      ? Math.max(0, Math.min(100, item.value as number))
                      : 0;
                    return (
                      <li
                        key={item.code}
                        className="grid grid-cols-[6rem_1fr_9rem] items-center gap-3 text-xs"
                      >
                        <span className="font-mono font-semibold">
                          {item.code}
                        </span>
                        {isMeasured ? (
                          <div className="relative h-5 w-full overflow-hidden rounded bg-muted">
                            <div
                              className="h-full rounded bg-primary transition-all"
                              style={{ width: `${barWidth}%` }}
                            />
                            <span className="sr-only">
                              {item.code}: {item.displayValue} out of 100,{' '}
                              {item.statusLabel}, coverage {item.coverageDisplay}
                            </span>
                          </div>
                        ) : (
                          <div className="flex h-5 w-full items-center rounded border border-dashed border-muted-foreground/40 px-2 text-[11px] text-muted-foreground">
                            <span>— {item.statusLabel}</span>
                          </div>
                        )}
                        <div className="flex items-center justify-end gap-1.5 text-right font-mono">
                          <span className="font-semibold">
                            {item.displayValue}
                          </span>
                          <span className="text-muted-foreground">
                            · {item.statusLabel}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <Separator />

              <div className="space-y-2">
                <h3 className="text-base font-semibold">
                  Detailed outcome breakdown &amp; evidence
                </h3>
                <Table>
                  <TableCaption>
                    Published PO1–PO11 attainment table (0–100 scale) for
                    snapshot v{activePublication.series_version}, PO set v
                    {activePublication.po_set_version}. Measured outcomes:{' '}
                    {measuredCount} of {profileItems.length}.
                  </TableCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Outcome</TableHead>
                      <TableHead scope="col">Score (0–100)</TableHead>
                      <TableHead scope="col">Coverage</TableHead>
                      <TableHead scope="col">Status</TableHead>
                      <TableHead scope="col">Evidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {profileItems.map((item) => {
                      const isExpanded = expandedCode === item.code;
                      const panelId = `po-evidence-${activePublication.id}-${item.code}`;
                      return (
                        <Fragment key={item.code}>
                          <TableRow>
                            <th
                              scope="row"
                              className="p-2 text-left align-middle font-medium"
                            >
                              <div className="font-mono font-semibold">
                                {item.code}
                              </div>
                              {item.label && (
                                <div className="text-xs font-normal text-muted-foreground">
                                  {item.label}
                                </div>
                              )}
                            </th>
                            <TableCell className="font-mono font-medium">
                              {item.displayValue}
                            </TableCell>
                            <TableCell className="font-mono">
                              {item.coverageDisplay}
                            </TableCell>
                            <TableCell>
                              <Badge variant={statusBadgeVariant(item.status)}>
                                {item.statusLabel}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                aria-expanded={isExpanded}
                                aria-controls={panelId}
                                onClick={() =>
                                  setExpandedCode((current) =>
                                    current === item.code ? null : item.code,
                                  )
                                }
                              >
                                {isExpanded
                                  ? 'Hide evidence'
                                  : 'Inspect evidence'}
                              </Button>
                            </TableCell>
                          </TableRow>
                          {isExpanded && (
                            <TableRow>
                              <TableCell colSpan={5} className="p-3">
                                <div
                                  id={panelId}
                                  role="region"
                                  aria-label={`Evidence for ${item.code}`}
                                >
                                  <EvidenceDrillDown
                                    item={item}
                                    publication={activePublication}
                                  />
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </Fragment>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {renderActions?.(activePublication.id)}
    </section>
  );
}
