'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  Calculator,
  CheckCircle2,
  RefreshCw,
  Send,
  ShieldAlert,
} from 'lucide-react';
import { errorMessage } from '@outcometrik/access';
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
import { getCatalogRows } from './api';
import {
  buildPublishIdempotencyKey,
  getCalculationRuns,
  getProgramPublications,
  parsePublicationConflict,
  publishCalculationRun,
  resolvePublicationFreshness,
  runProgramCalculation,
  type CalculationRun,
  type PublicationAudience,
} from './publications-api';
import { getAllSyllabi, getProgramOutcomeSets } from '../syllabus/api';
import { getCoordinatorWorkspace } from '../workspace/api';

function shortHash(hash: string): string {
  return hash.length > 12 ? hash.slice(0, 12) : hash;
}

export function CoordinatorPublicationsManager() {
  const queryClient = useQueryClient();
  const programSelectId = useId();
  const audienceSelectId = useId();
  const termSelectId = useId();

  const workspaceQuery = useQuery({
    queryKey: ['academic', 'coordinator'],
    queryFn: ({ signal }) => getCoordinatorWorkspace(signal),
  });

  const programs = useMemo(
    () => workspaceQuery.data?.programs ?? [],
    [workspaceQuery.data],
  );
  const offerings = useMemo(
    () => workspaceQuery.data?.offerings ?? [],
    [workspaceQuery.data],
  );

  const [selectedProgramId, setSelectedProgramId] = useState<string>('');
  const activeProgramId =
    selectedProgramId && programs.some((p) => p.id === selectedProgramId)
      ? selectedProgramId
      : (programs[0]?.id ?? '');

  const [audience, setAudience] = useState<PublicationAudience>('faculty');
  const [selectedTermId, setSelectedTermId] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [conflictState, setConflictState] = useState<{
    code: string;
    message: string;
  } | null>(null);

  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', activeProgramId],
    queryFn: ({ signal }) => getProgramOutcomeSets(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const syllabiQuery = useQuery({
    queryKey: ['academic', 'syllabi', 'all'],
    queryFn: ({ signal }) => getAllSyllabi(undefined, signal),
    enabled: Boolean(activeProgramId),
  });

  const termsQuery = useQuery({
    queryKey: ['academic', 'terms', 'all'],
    queryFn: ({ signal }) => getCatalogRows('terms', {}, signal),
    enabled: Boolean(activeProgramId),
  });

  const runsQuery = useQuery({
    queryKey: ['academic', 'calculation-runs', activeProgramId],
    queryFn: ({ signal }) => getCalculationRuns(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const publicationsQuery = useQuery({
    queryKey: ['academic', 'publications', activeProgramId],
    queryFn: ({ signal }) => getProgramPublications(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const activePoSet = useMemo(
    () => (poSetsQuery.data ?? []).find((s) => s.active) ?? null,
    [poSetsQuery.data],
  );

  const programOfferings = useMemo(
    () => offerings.filter((o) => o.program_id === activeProgramId),
    [offerings, activeProgramId],
  );

  const syllabusReadiness = useMemo(() => {
    const allSyllabi = syllabiQuery.data ?? [];
    let approvedOfferings = 0;
    let draftOnlyOfferings = 0;
    for (const off of programOfferings) {
      const offSyllabi = allSyllabi.filter((s) => s.offering === off.id);
      if (offSyllabi.some((s) => s.status === 'approved')) {
        approvedOfferings += 1;
      } else if (offSyllabi.some((s) => s.status === 'draft')) {
        draftOnlyOfferings += 1;
      }
    }
    return {
      totalOfferings: programOfferings.length,
      approvedOfferings,
      draftOnlyOfferings,
    };
  }, [programOfferings, syllabiQuery.data]);

  const programRuns = useMemo(
    () =>
      (runsQuery.data ?? [])
        .filter((r) => r.scope_kind === 'program')
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [runsQuery.data],
  );
  const latestRun: CalculationRun | null = programRuns[0] ?? null;

  const publications = useMemo(
    () =>
      [...(publicationsQuery.data ?? [])].sort((a, b) => {
        if (b.series_version !== a.series_version) {
          return b.series_version - a.series_version;
        }
        return (b.published_at ?? '').localeCompare(a.published_at ?? '');
      }),
    [publicationsQuery.data],
  );

  // Current highest series version for program-level publications of the chosen audience
  const currentSeriesVersion = useMemo(() => {
    const matching = publications.filter(
      (p) => p.offering === null && p.audience === audience,
    );
    return matching.reduce((max, p) => Math.max(max, p.series_version), 0);
  }, [publications, audience]);

  const nextSeriesVersion = currentSeriesVersion + 1;

  const terms = useMemo(
    () =>
      (termsQuery.data ?? []).map((t) => ({
        id: t.id,
        label: `${String(t.year ?? '')} ${String(t.season ?? '').replace(/^./, (c) => c.toUpperCase())}`.trim(),
      })),
    [termsQuery.data],
  );

  const runCalculationMutation = useMutation({
    mutationFn: (programId: string) => runProgramCalculation(programId),
    onSuccess: async (run) => {
      setConflictState(null);
      setStatusMessage(
        `Calculation run ${run.id.slice(0, 8)} completed (PO-Set v${run.po_set_version}).`,
      );
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'calculation-runs', activeProgramId],
      });
    },
  });

  const runAndPublishMutation = useMutation({
    mutationFn: async (args: {
      programId: string;
      audience: PublicationAudience;
      termId: string | null;
      expectedSeriesVersion: number;
    }) => {
      // Step 1: Run deterministic program calculation
      const run = await runProgramCalculation(args.programId);
      // Step 2: Publish immutable snapshot with idempotency key
      const idempotencyKey = buildPublishIdempotencyKey({
        programId: args.programId,
        runId: run.id,
        expectedSeriesVersion: args.expectedSeriesVersion,
        audience: args.audience,
      });
      const publication = await publishCalculationRun({
        run: run.id,
        expected_series_version: args.expectedSeriesVersion,
        expected_input_hash: run.input_hash,
        audience: args.audience,
        idempotency_key: idempotencyKey,
        term: args.termId || null,
      });
      return { run, publication };
    },
    onSuccess: async ({ publication }) => {
      setConflictState(null);
      setStatusMessage(
        `Published Series v${publication.series_version} (${publication.audience}) — Publication ${publication.id.slice(0, 8)}.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['academic', 'calculation-runs', activeProgramId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['academic', 'publications', activeProgramId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['reports', 'coordinator-publications'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['reports', 'cohort-analytics'],
        }),
      ]);
    },
    onError: (err) => {
      const parsed = parsePublicationConflict(err);
      if (parsed.isConflict) {
        setConflictState({
          code: parsed.code ?? 'stale_input',
          message: parsed.message,
        });
      }
    },
  });

  if (workspaceQuery.isPending) {
    return (
      <div className="space-y-4" role="status">
        <p className="text-sm text-muted-foreground">
          Loading calculation runs and publications…
        </p>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (workspaceQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Unable to load publications workspace</AlertTitle>
        <AlertDescription>{errorMessage(workspaceQuery.error)}</AlertDescription>
      </Alert>
    );
  }

  if (programs.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No authorized programs</EmptyTitle>
          <EmptyDescription>
            No active programs are assigned to your coordinator scope.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  const hasActivePoSet = Boolean(activePoSet);
  const hasApprovedSyllabus = syllabusReadiness.approvedOfferings > 0;
  const latestRunIncomplete =
    latestRun !== null && !latestRun.is_complete_for_publication;
  const isBusy =
    runCalculationMutation.isPending || runAndPublishMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Program Scope Selector */}
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)]">
        <Field className="min-w-[260px] max-w-md flex-1">
          <FieldLabel htmlFor={programSelectId}>Program scope</FieldLabel>
          <NativeSelect
            id={programSelectId}
            value={activeProgramId}
            onChange={(e) => {
              setSelectedProgramId(e.target.value);
              setConflictState(null);
              setStatusMessage(null);
            }}
          >
            {programs.map((program) => (
              <NativeSelectOption key={program.id} value={program.id}>
                {program.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {activePoSet && (
            <Badge variant="secondary" className="tabular-mono">
              Active PO-Set v{activePoSet.version}
            </Badge>
          )}
          <Badge variant="outline" className="tabular-mono">
            Next series: v{nextSeriesVersion} ({audience})
          </Badge>
        </div>
      </div>

      {/* Pre-publication Readiness Gates + Run & Publish Workflow */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Readiness Gates */}
        <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
          <CardHeader className="border-b border-border/70 pb-4">
            <CardTitle>
              <h2 className="text-base font-semibold tracking-tight">
                Pre-publication readiness gates
              </h2>
            </CardTitle>
            <CardDescription>
              Authoritative prerequisites verified before sealing an immutable
              publication series.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {/* Gate 1: Active PO set */}
            <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
              <div className="flex items-start gap-2.5">
                {hasActivePoSet ? (
                  <CheckCircle2
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                    aria-hidden="true"
                  />
                ) : (
                  <ShieldAlert
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-danger-fg)]"
                    aria-hidden="true"
                  />
                )}
                <div>
                  <p className="text-sm font-medium">Active PO1–PO11 set</p>
                  <p className="text-xs text-muted-foreground">
                    {activePoSet
                      ? `PO-Set v${activePoSet.version} active (effective ${activePoSet.effective_date ?? 'set'}).`
                      : 'No active PO set found. Activate a PO set first.'}
                  </p>
                </div>
              </div>
              <StatusDot
                variant={hasActivePoSet ? 'success' : 'danger'}
                label={hasActivePoSet ? 'Ready' : 'Blocked'}
              />
            </div>

            {/* Gate 2: Approved syllabi */}
            <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
              <div className="flex items-start gap-2.5">
                {hasApprovedSyllabus ? (
                  <CheckCircle2
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                    aria-hidden="true"
                  />
                ) : (
                  <ShieldAlert
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-danger-fg)]"
                    aria-hidden="true"
                  />
                )}
                <div>
                  <p className="text-sm font-medium">Approved syllabi</p>
                  <p className="text-xs text-muted-foreground">
                    {syllabusReadiness.approvedOfferings} of{' '}
                    {syllabusReadiness.totalOfferings} offerings have an
                    approved locked syllabus.
                    {syllabusReadiness.draftOnlyOfferings > 0
                      ? ` ${syllabusReadiness.draftOnlyOfferings} offering(s) still have unapproved drafts.`
                      : ''}
                  </p>
                </div>
              </div>
              <StatusDot
                variant={
                  hasApprovedSyllabus
                    ? syllabusReadiness.draftOnlyOfferings > 0
                      ? 'warning'
                      : 'success'
                    : 'danger'
                }
                label={
                  hasApprovedSyllabus
                    ? syllabusReadiness.draftOnlyOfferings > 0
                      ? 'Partial'
                      : 'Ready'
                    : 'Blocked'
                }
              />
            </div>

            {/* Gate 3: Released grades & blocking absents */}
            <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
              <div className="flex items-start gap-2.5">
                {latestRun === null ? (
                  <AlertTriangle
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-warn-fg)]"
                    aria-hidden="true"
                  />
                ) : latestRunIncomplete ? (
                  <AlertTriangle
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-warn-fg)]"
                    aria-hidden="true"
                  />
                ) : (
                  <CheckCircle2
                    className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                    aria-hidden="true"
                  />
                )}
                <div>
                  <p className="text-sm font-medium">
                    Released grades &amp; blocking absents
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {latestRun === null
                      ? 'No program calculation run yet. Running calculation validates released grades and blocking ABSENT states.'
                      : latestRunIncomplete
                        ? 'Latest run flagged incomplete grades or blocking ABSENT records. Unmeasured students will be excluded (never coerced to zero).'
                        : `Latest run ${latestRun.id.slice(0, 8)} is complete for publication (policy ${latestRun.policy_version}).`}
                  </p>
                </div>
              </div>
              <StatusDot
                variant={
                  latestRun === null
                    ? 'neutral'
                    : latestRunIncomplete
                      ? 'warning'
                      : 'success'
                }
                label={
                  latestRun === null
                    ? 'Pending run'
                    : latestRunIncomplete
                      ? 'Absents warning'
                      : 'Complete'
                }
              />
            </div>
          </CardContent>
        </Card>

        {/* Run & Publish Workflow Card */}
        <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
          <CardHeader className="border-b border-border/70 pb-4">
            <CardTitle>
              <h2 className="text-base font-semibold tracking-tight">
                Run calculation &amp; publish immutable series
              </h2>
            </CardTitle>
            <CardDescription>
              Executes the deterministic decimal scoring kernel and seals Series
              v{nextSeriesVersion}. Existing publications remain immutable.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <FieldGroup className="grid gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor={audienceSelectId}>Audience</FieldLabel>
                <NativeSelect
                  id={audienceSelectId}
                  value={audience}
                  disabled={isBusy}
                  onChange={(e) =>
                    setAudience(e.target.value as PublicationAudience)
                  }
                >
                  <NativeSelectOption value="faculty">
                    Faculty &amp; accreditation
                  </NativeSelectOption>
                  <NativeSelectOption value="student">
                    Student portal release
                  </NativeSelectOption>
                </NativeSelect>
              </Field>

              <Field>
                <FieldLabel htmlFor={termSelectId}>
                  Term tag (optional)
                </FieldLabel>
                <NativeSelect
                  id={termSelectId}
                  value={selectedTermId}
                  disabled={isBusy}
                  onChange={(e) => setSelectedTermId(e.target.value)}
                >
                  <NativeSelectOption value="">
                    Cumulative (all terms)
                  </NativeSelectOption>
                  {terms.map((t) => (
                    <NativeSelectOption key={t.id} value={t.id}>
                      {t.label}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
            </FieldGroup>

            {latestRun && (
              <div className="rounded-[var(--radius-input,6px)] border border-border/80 bg-[var(--surface-subtle)]/50 p-3 text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-foreground">
                    Latest calculation run
                  </span>
                  <span className="tabular-mono text-muted-foreground">
                    Run {latestRun.id.slice(0, 8)} · PO-Set v
                    {latestRun.po_set_version}
                  </span>
                </div>
                <p className="tabular-mono mt-1 text-[11px] text-muted-foreground">
                  Input hash: {shortHash(latestRun.input_hash)} · Engine{' '}
                  {latestRun.engine_version} · Policy {latestRun.policy_version}
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={isBusy || !hasActivePoSet}
                onClick={() => runCalculationMutation.mutate(activeProgramId)}
              >
                <Calculator className="size-4" aria-hidden="true" />
                {runCalculationMutation.isPending
                  ? 'Calculating…'
                  : 'Run calculation only'}
              </Button>

              <Button
                type="button"
                disabled={isBusy || !hasActivePoSet || !hasApprovedSyllabus}
                onClick={() =>
                  runAndPublishMutation.mutate({
                    programId: activeProgramId,
                    audience,
                    termId: selectedTermId || null,
                    expectedSeriesVersion: currentSeriesVersion,
                  })
                }
              >
                <Send className="size-4" aria-hidden="true" />
                {runAndPublishMutation.isPending
                  ? `Publishing Series v${nextSeriesVersion}…`
                  : `Run calculation & publish Series v${nextSeriesVersion}`}
              </Button>
            </div>

            {statusMessage && (
              <p
                role="status"
                className="text-xs font-medium text-[var(--status-success-fg)]"
              >
                {statusMessage}
              </p>
            )}

            {conflictState && (
              <Alert variant="destructive">
                <AlertTitle>
                  Publication conflict ({conflictState.code})
                </AlertTitle>
                <AlertDescription className="space-y-2">
                  <p>{conflictState.message}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      setConflictState(null);
                      await Promise.all([
                        queryClient.invalidateQueries({
                          queryKey: [
                            'academic',
                            'calculation-runs',
                            activeProgramId,
                          ],
                        }),
                        queryClient.invalidateQueries({
                          queryKey: [
                            'academic',
                            'publications',
                            activeProgramId,
                          ],
                        }),
                      ]);
                      runCalculationMutation.mutate(activeProgramId);
                    }}
                  >
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                    Re-run calculation &amp; refresh
                  </Button>
                </AlertDescription>
              </Alert>
            )}

            {runCalculationMutation.isError && (
              <Alert variant="destructive">
                <AlertTitle>Calculation failed</AlertTitle>
                <AlertDescription>
                  {errorMessage(runCalculationMutation.error)}
                </AlertDescription>
              </Alert>
            )}

            {runAndPublishMutation.isError && !conflictState && (
              <Alert variant="destructive">
                <AlertTitle>Publication failed</AlertTitle>
                <AlertDescription>
                  {parsePublicationConflict(runAndPublishMutation.error).message}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Immutable Publication Series Table */}
      <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
        <CardHeader className="border-b border-border/70 pb-4">
          <CardTitle>
            <h2 className="text-lg font-semibold tracking-tight">
              Immutable publication series
            </h2>
          </CardTitle>
          <CardDescription>
            Historical and current snapshots with cryptographic input manifest
            hashes. Publishing Series v{nextSeriesVersion} clears STALE status
            without altering prior series.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-5">
          {publicationsQuery.isPending ? (
            <div className="space-y-2" role="status">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : publicationsQuery.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to load publications</AlertTitle>
              <AlertDescription>
                {errorMessage(publicationsQuery.error)}
              </AlertDescription>
            </Alert>
          ) : publications.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No publications yet</EmptyTitle>
                <EmptyDescription>
                  Run calculation and publish Series v1 to create the first
                  immutable outcome snapshot for this program.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
              <Table>
                <TableCaption className="pb-3">
                  Immutable publication series for the selected program.
                </TableCaption>
                <TableHeader className="bg-[var(--surface-subtle)]">
                  <TableRow>
                    <TableHead scope="col">Series</TableHead>
                    <TableHead scope="col">Scope &amp; term</TableHead>
                    <TableHead scope="col">PO-Set</TableHead>
                    <TableHead scope="col">Audience</TableHead>
                    <TableHead scope="col">Freshness</TableHead>
                    <TableHead scope="col">Published at</TableHead>
                    <TableHead scope="col">Manifest hash</TableHead>
                    <TableHead scope="col" className="text-right">
                      Inspect
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {publications.map((pub) => {
                    const freshness = resolvePublicationFreshness(
                      pub,
                      publications,
                    );
                    return (
                      <TableRow key={pub.id}>
                        <th
                          scope="row"
                          className="tabular-mono p-2.5 text-left align-middle font-semibold whitespace-nowrap"
                        >
                          Series v{pub.series_version}
                          <span className="block text-[11px] font-normal text-muted-foreground">
                            {pub.id.slice(0, 8)}
                          </span>
                        </th>
                        <TableCell className="text-xs">
                          <span className="font-medium">
                            {pub.offering_label ?? 'Program cumulative'}
                          </span>
                          <span className="block text-muted-foreground">
                            {pub.term_label ?? 'All terms'}
                          </span>
                        </TableCell>
                        <TableCell className="tabular-mono text-xs">
                          PO-Set v{pub.po_set_version}
                        </TableCell>
                        <TableCell className="text-xs capitalize">
                          {pub.audience}
                        </TableCell>
                        <TableCell>
                          {freshness === 'current' ? (
                            <StatusDot variant="success" label="Current" />
                          ) : freshness === 'stale' ? (
                            <StaleTag label="Stale" />
                          ) : (
                            <StatusDot variant="neutral" label="Historical" />
                          )}
                        </TableCell>
                        <TableCell className="tabular-mono text-xs text-muted-foreground whitespace-nowrap">
                          {pub.published_at
                            ? pub.published_at.slice(0, 16).replace('T', ' ')
                            : '—'}
                        </TableCell>
                        <TableCell
                          className="tabular-mono text-xs text-muted-foreground"
                          title={pub.input_hash}
                        >
                          {shortHash(pub.input_hash)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button asChild variant="ghost" size="sm">
                            <a
                              href={`/coordinator/analytics?program=${encodeURIComponent(pub.program)}&publication=${encodeURIComponent(pub.id)}`}
                            >
                              Analytics
                              <ArrowUpRight
                                className="size-3.5"
                                aria-hidden="true"
                              />
                            </a>
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
