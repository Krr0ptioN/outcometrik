'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useMemo, useState } from 'react';
import { CheckCircle2, Lock, ShieldAlert } from 'lucide-react';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
  NotAssessedText,
  Skeleton,
  StatusDot,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import { getCatalogRows } from '../catalog/api';
import { getCoordinatorWorkspace } from '../workspace/api';
import {
  approveSyllabus,
  deleteSyllabusPOContribution,
  getAllSyllabi,
  getProgramOutcomeSets,
  getProgramOutcomes,
  getSyllabusMappingValidation,
  saveSyllabusPOContribution,
  type CoursePOContribution,
  type ProgramOutcome,
  type Syllabus,
} from './api';

export type RelevanceWeightValidation =
  | { ok: true; value: number | null }
  | { ok: false; error: string };

/**
 * Validates a Course→PO relevance weight input.
 * Empty string clears the weight; otherwise must be an integer 1–5.
 */
export function validateCoursePoRelevanceWeight(
  raw: string,
): RelevanceWeightValidation {
  const trimmed = raw.trim();
  if (trimmed === '') return { ok: true, value: null };
  if (!/^[1-5]$/.test(trimmed)) {
    return {
      ok: false,
      error: 'Relevance weight must be an integer between 1 and 5.',
    };
  }
  return { ok: true, value: Number(trimmed) };
}

type QueueFilter = 'draft' | 'approved' | 'all';

function statusBadge(status: Syllabus['status']) {
  if (status === 'approved') {
    return <StatusDot variant="success" label="Approved (locked)" />;
  }
  if (status === 'draft') {
    return <StatusDot variant="warning" label="Pending draft" />;
  }
  return <StatusDot variant="neutral" label="Retired" />;
}

export function CoordinatorApprovalsPanel() {
  const queryClient = useQueryClient();
  const programSelectId = useId();

  const workspaceQuery = useQuery({
    queryKey: ['academic', 'coordinator'],
    queryFn: ({ signal }) => getCoordinatorWorkspace(signal),
  });

  const syllabiQuery = useQuery({
    queryKey: ['academic', 'syllabi', 'all'],
    queryFn: ({ signal }) => getAllSyllabi(undefined, signal),
    enabled: Boolean(workspaceQuery.data),
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

  const [queueFilter, setQueueFilter] = useState<QueueFilter>('draft');
  const [selectedSyllabusId, setSelectedSyllabusId] = useState<string>('');
  const [confirmApproveOpen, setConfirmApproveOpen] = useState(false);

  // Course→PO Relevance Weight local draft cells keyed by `${syllabusId}:${poId}`
  const [weightDrafts, setWeightDrafts] = useState<Record<string, string>>({});
  const [weightErrors, setWeightErrors] = useState<Record<string, string>>({});
  const [matrixFeedback, setMatrixFeedback] = useState<string | null>(null);

  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', activeProgramId],
    queryFn: ({ signal }) => getProgramOutcomeSets(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const activePoSet = useMemo(() => {
    const sets = poSetsQuery.data ?? [];
    return sets.find((s) => s.active) ?? sets[0] ?? null;
  }, [poSetsQuery.data]);

  const outcomesQuery = useQuery({
    queryKey: ['academic', 'po-set-outcomes', activePoSet?.id ?? null],
    queryFn: ({ signal }) => getProgramOutcomes(activePoSet?.id ?? '', signal),
    enabled: Boolean(activePoSet?.id),
  });

  const programCoursesQuery = useQuery({
    queryKey: ['academic', 'program-courses', 'all'],
    queryFn: ({ signal }) => getCatalogRows('program-courses', {}, signal),
    enabled: Boolean(activeProgramId),
  });

  const coursesQuery = useQuery({
    queryKey: ['academic', 'courses', 'all'],
    queryFn: ({ signal }) => getCatalogRows('courses', {}, signal),
    enabled: Boolean(activeProgramId),
  });

  const offeringsQuery = useQuery({
    queryKey: ['academic', 'offerings', activeProgramId],
    queryFn: ({ signal }) =>
      getCatalogRows('offerings', { program: activeProgramId }, signal),
    enabled: Boolean(activeProgramId),
  });

  const programOfferings = useMemo(
    () => offerings.filter((o) => o.program_id === activeProgramId),
    [offerings, activeProgramId],
  );
  const offeringById = useMemo(
    () => new Map(programOfferings.map((o) => [o.id, o])),
    [programOfferings],
  );

  const programSyllabi = useMemo(() => {
    const all = syllabiQuery.data ?? [];
    return all
      .filter((s) => offeringById.has(s.offering))
      .sort((a, b) => {
        if (a.status === 'draft' && b.status !== 'draft') return -1;
        if (a.status !== 'draft' && b.status === 'draft') return 1;
        return b.version - a.version;
      });
  }, [syllabiQuery.data, offeringById]);

  const filteredSyllabi = useMemo(() => {
    if (queueFilter === 'all') return programSyllabi;
    return programSyllabi.filter((s) => s.status === queueFilter);
  }, [programSyllabi, queueFilter]);

  const activeSyllabus =
    filteredSyllabi.find((s) => s.id === selectedSyllabusId) ??
    filteredSyllabi[0] ??
    null;

  const validationQuery = useQuery({
    queryKey: ['academic', 'syllabus-validation', activeSyllabus?.id ?? null],
    queryFn: ({ signal }) =>
      getSyllabusMappingValidation(activeSyllabus?.id ?? '', signal),
    enabled: Boolean(activeSyllabus?.id),
  });

  const approveMutation = useMutation({
    mutationFn: (syllabusId: string) => approveSyllabus(syllabusId),
    onSuccess: async () => {
      setConfirmApproveOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['academic', 'syllabi'] }),
        queryClient.invalidateQueries({
          queryKey: ['academic', 'syllabus-validation'],
        }),
      ]);
    },
  });

  const saveWeightMutation = useMutation({
    mutationFn: async (args: {
      syllabusId: string;
      programOutcomeId: string;
      weight: number | null;
      existingId?: string;
    }) => {
      if (args.weight === null) {
        if (args.existingId) {
          await deleteSyllabusPOContribution(args.syllabusId, args.existingId);
        }
        return;
      }
      await saveSyllabusPOContribution(
        args.syllabusId,
        { program_outcome: args.programOutcomeId, weight: args.weight },
        args.existingId,
      );
    },
    onSuccess: async (_, vars) => {
      const cellKey = `${vars.syllabusId}:${vars.programOutcomeId}`;
      setWeightDrafts((prev) => {
        const next = { ...prev };
        delete next[cellKey];
        return next;
      });
      setWeightErrors((prev) => {
        const next = { ...prev };
        delete next[cellKey];
        return next;
      });
      setMatrixFeedback('Course→PO relevance weight saved.');
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'syllabi'],
      });
    },
  });

  // Build M:N-aware course rows linked to the selected program
  const coursePoRows = useMemo(() => {
    const allLinks = programCoursesQuery.data ?? [];
    const allCourses = coursesQuery.data ?? [];
    const rawOfferings = offeringsQuery.data ?? [];
    const courseById = new Map(allCourses.map((c) => [c.id, c]));
    const programLabelById = new Map(programs.map((p) => [p.id, p.label]));

    // Map courseId -> list of program labels (M:N awareness)
    const coursePrograms = new Map<string, string[]>();
    for (const link of allLinks) {
      const courseId = String(link.course ?? '');
      const progId = String(link.program ?? '');
      if (!courseId || !progId) continue;
      const existing = coursePrograms.get(courseId) ?? [];
      const label = programLabelById.get(progId) ?? progId.slice(0, 8);
      if (!existing.includes(label)) existing.push(label);
      coursePrograms.set(courseId, existing);
    }

    const linkedCourseIds = Array.from(
      new Set(
        allLinks
          .filter((link) => String(link.program ?? '') === activeProgramId)
          .map((link) => String(link.course ?? ''))
          .filter(Boolean),
      ),
    );

    const syllabiByOffering = new Map<string, Syllabus[]>();
    for (const s of programSyllabi) {
      const list = syllabiByOffering.get(s.offering) ?? [];
      list.push(s);
      syllabiByOffering.set(s.offering, list);
    }

    return linkedCourseIds.map((courseId) => {
      const courseRow = courseById.get(courseId);
      const code = String(courseRow?.code ?? courseId.slice(0, 8));
      const title = String(courseRow?.title ?? 'Untitled course');

      // Find offerings for this course in activeProgramId
      const matchingOfferingIds = rawOfferings
        .filter((o) => String(o.course ?? '') === courseId)
        .map((o) => o.id);

      const courseSyllabi = matchingOfferingIds.flatMap(
        (oid) => syllabiByOffering.get(oid) ?? [],
      );
      // Prefer editable draft syllabus, otherwise latest approved syllabus
      const targetSyllabus =
        courseSyllabi.find((s) => s.status === 'draft') ??
        courseSyllabi
          .filter((s) => s.status === 'approved')
          .sort((a, b) => b.version - a.version)[0] ??
        null;

      const contributionsByPo = new Map<string, CoursePOContribution>();
      for (const c of targetSyllabus?.po_contributions ?? []) {
        contributionsByPo.set(c.program_outcome, c);
      }

      return {
        courseId,
        code,
        title,
        linkedPrograms: coursePrograms.get(courseId) ?? [],
        syllabus: targetSyllabus,
        contributionsByPo,
      };
    });
  }, [
    programCoursesQuery.data,
    coursesQuery.data,
    offeringsQuery.data,
    programs,
    activeProgramId,
    programSyllabi,
  ]);

  const programOutcomes: ProgramOutcome[] = useMemo(
    () =>
      [...(outcomesQuery.data ?? [])].sort((a, b) => a.order - b.order),
    [outcomesQuery.data],
  );

  const poById = useMemo(
    () => new Map(programOutcomes.map((po) => [po.id, po])),
    [programOutcomes],
  );

  if (workspaceQuery.isPending) {
    return (
      <div className="space-y-4" role="status">
        <p className="text-sm text-muted-foreground">
          Loading syllabus approval queue…
        </p>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (workspaceQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Unable to load coordinator approvals</AlertTitle>
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
            You do not have coordinator approval access for any active program.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  const draftCount = programSyllabi.filter((s) => s.status === 'draft').length;
  const approvedCount = programSyllabi.filter(
    (s) => s.status === 'approved',
  ).length;

  function handleWeightBlur(
    syllabusId: string,
    programOutcomeId: string,
    existing?: CoursePOContribution,
  ) {
    const cellKey = `${syllabusId}:${programOutcomeId}`;
    const raw = weightDrafts[cellKey];
    if (raw === undefined) return;
    const validation = validateCoursePoRelevanceWeight(raw);
    if (!validation.ok) {
      setWeightErrors((prev) => ({ ...prev, [cellKey]: validation.error }));
      return;
    }
    const existingVal = existing?.weight ?? null;
    if (validation.value === existingVal) {
      setWeightDrafts((prev) => {
        const next = { ...prev };
        delete next[cellKey];
        return next;
      });
      setWeightErrors((prev) => {
        const next = { ...prev };
        delete next[cellKey];
        return next;
      });
      return;
    }
    setMatrixFeedback(null);
    saveWeightMutation.mutate({
      syllabusId,
      programOutcomeId,
      weight: validation.value,
      existingId: existing?.id,
    });
  }

  return (
    <div className="space-y-6">
      {/* Program Scope Filter Bar */}
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)]">
        <Field className="min-w-[260px] max-w-md flex-1">
          <FieldLabel htmlFor={programSelectId}>Program scope</FieldLabel>
          <NativeSelect
            id={programSelectId}
            value={activeProgramId}
            onChange={(e) => {
              setSelectedProgramId(e.target.value);
              setSelectedSyllabusId('');
            }}
          >
            {programs.map((program) => (
              <NativeSelectOption key={program.id} value={program.id}>
                {program.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <div className="flex flex-wrap items-center gap-3 text-xs">
          <Badge variant="outline" className="tabular-mono">
            {draftCount} pending draft{draftCount === 1 ? '' : 's'}
          </Badge>
          <Badge variant="secondary" className="tabular-mono">
            {approvedCount} approved &amp; locked
          </Badge>
          {activePoSet && (
            <Badge variant="outline" className="tabular-mono">
              Active PO-Set v{activePoSet.version}
            </Badge>
          )}
        </div>
      </div>

      {/* Section 1: Pending Syllabus Approval Queue + Full Matrix Preview */}
      <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
        <CardHeader className="border-b border-border/70 pb-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>
                <h2 className="text-lg font-semibold tracking-tight">
                  Syllabus approval queue
                </h2>
              </CardTitle>
              <CardDescription>
                Inspect A×LO and LO×PO mapping matrices and validation checks
                before locking a syllabus version.
              </CardDescription>
            </div>
            <div
              role="tablist"
              aria-label="Filter syllabus queue"
              className="inline-flex items-center rounded-[var(--radius-input,6px)] border border-border bg-muted/50 p-0.5"
            >
              {(
                [
                  { id: 'draft', label: `Pending drafts (${draftCount})` },
                  { id: 'approved', label: `Approved (${approvedCount})` },
                  { id: 'all', label: `All (${programSyllabi.length})` },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={queueFilter === tab.id}
                  onClick={() => setQueueFilter(tab.id)}
                  className={`rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
                    queueFilter === tab.id
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-5">
          {syllabiQuery.isPending ? (
            <div className="space-y-3" role="status">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-44 w-full" />
            </div>
          ) : syllabiQuery.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to load syllabi</AlertTitle>
              <AlertDescription>
                {errorMessage(syllabiQuery.error)}
              </AlertDescription>
            </Alert>
          ) : filteredSyllabi.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>
                  {queueFilter === 'draft'
                    ? 'No draft syllabi awaiting approval'
                    : 'No syllabi in this filter'}
                </EmptyTitle>
                <EmptyDescription>
                  Switch to Approved or All to inspect locked syllabus versions.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              {/* Left Queue List */}
              <div
                role="listbox"
                aria-label="Syllabi in queue"
                className="space-y-2"
              >
                {filteredSyllabi.map((syllabus) => {
                  const offering = offeringById.get(syllabus.offering);
                  const isSelected = activeSyllabus?.id === syllabus.id;
                  return (
                    <button
                      key={syllabus.id}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => setSelectedSyllabusId(syllabus.id)}
                      className={`w-full rounded-[var(--radius-card,10px)] border p-3 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring ${
                        isSelected
                          ? 'border-[var(--accent-border)] bg-[var(--accent-soft)]'
                          : 'border-border bg-card hover:bg-[var(--surface-hover)]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                          {offering?.label ?? syllabus.offering.slice(0, 8)}
                        </span>
                        <Badge
                          variant="outline"
                          className="tabular-mono shrink-0 text-[11px]"
                        >
                          v{syllabus.version}
                        </Badge>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {offering?.term ?? ''}
                      </p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        {statusBadge(syllabus.status)}
                        {syllabus.po_set_version !== null && (
                          <span className="tabular-mono text-[11px] text-muted-foreground">
                            PO-Set v{syllabus.po_set_version}
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Right Inspection & Approval Detail */}
              {activeSyllabus && (
                <div className="min-w-0 space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-[var(--surface-subtle)]/40 p-4">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold tracking-tight">
                          {offeringById.get(activeSyllabus.offering)?.label ??
                            'Offering'}{' '}
                          — Syllabus v{activeSyllabus.version}
                        </h3>
                        {statusBadge(activeSyllabus.status)}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {offeringById.get(activeSyllabus.offering)?.course} ·{' '}
                        {offeringById.get(activeSyllabus.offering)?.term}
                        {activeSyllabus.approved_at
                          ? ` · Locked ${activeSyllabus.approved_at.slice(0, 10)}`
                          : ''}
                      </p>
                    </div>

                    {activeSyllabus.status === 'draft' ? (
                      <Button
                        type="button"
                        onClick={() => setConfirmApproveOpen(true)}
                        disabled={
                          approveMutation.isPending ||
                          (validationQuery.data !== undefined &&
                            !validationQuery.data.is_valid_for_approval)
                        }
                      >
                        <Lock className="size-4" aria-hidden="true" />
                        Approve &amp; lock
                      </Button>
                    ) : (
                      <Badge
                        variant="secondary"
                        className="inline-flex items-center gap-1.5"
                      >
                        <Lock className="size-3" aria-hidden="true" />
                        Immutable locked version
                      </Badge>
                    )}
                  </div>

                  {approveMutation.isError && (
                    <Alert variant="destructive">
                      <AlertTitle>Approval blocked</AlertTitle>
                      <AlertDescription>
                        {errorMessage(approveMutation.error)}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Mapping Validation Summary */}
                  {validationQuery.isPending ? (
                    <Skeleton className="h-16 w-full" />
                  ) : validationQuery.data ? (
                    <div
                      className={`rounded-[var(--radius-card,10px)] border p-3.5 text-sm ${
                        validationQuery.data.is_valid_for_approval
                          ? 'border-[var(--status-success-border)] bg-[var(--status-success-bg)]/60'
                          : 'border-[var(--status-danger-border)] bg-[var(--status-danger-bg)]/60'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="inline-flex items-center gap-2 font-medium">
                          {validationQuery.data.is_valid_for_approval ? (
                            <>
                              <CheckCircle2
                                className="size-4 text-[var(--status-success-fg)]"
                                aria-hidden="true"
                              />
                              Ready for approval — all mapping rules satisfied
                            </>
                          ) : (
                            <>
                              <ShieldAlert
                                className="size-4 text-[var(--status-danger-fg)]"
                                aria-hidden="true"
                              />
                              Validation blockers must be resolved before
                              locking
                            </>
                          )}
                        </span>
                        <span className="tabular-mono text-xs text-muted-foreground">
                          Mapped LOs:{' '}
                          {
                            validationQuery.data.lo_statuses.filter(
                              (l) => l.status === 'MAPPED',
                            ).length
                          }
                          /{validationQuery.data.lo_statuses.length} · Assessed
                          POs:{' '}
                          {
                            validationQuery.data.po_statuses.filter(
                              (p) => p.status === 'ASSESSED',
                            ).length
                          }
                          /{validationQuery.data.po_statuses.length}
                        </span>
                      </div>
                      {validationQuery.data.errors.length > 0 && (
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--status-danger-fg)]">
                          {validationQuery.data.errors.map((err, idx) => (
                            <li key={idx}>{err}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ) : null}

                  {/* A×LO Matrix Preview */}
                  <section className="space-y-2">
                    <h4 className="text-sm font-semibold">
                      Assessment × Learning Outcome (A×LO) matrix preview
                    </h4>
                    <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                      <Table>
                        <TableCaption className="pb-2">
                          A×LO weights for syllabus v{activeSyllabus.version}.
                        </TableCaption>
                        <TableHeader className="bg-[var(--surface-subtle)]">
                          <TableRow>
                            <TableHead scope="col">Assessment</TableHead>
                            {activeSyllabus.learning_outcomes.map((lo) => (
                              <TableHead
                                key={lo.id}
                                scope="col"
                                className="tabular-mono text-right"
                              >
                                {lo.code}
                              </TableHead>
                            ))}
                            <TableHead scope="col" className="text-right">
                              Row sum
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {activeSyllabus.assessments.map((assessment) => {
                            const rowMappings = (
                              activeSyllabus.assessment_lo_mappings ?? []
                            ).filter(
                              (m) =>
                                m.assessment === assessment.id && m.is_active,
                            );
                            const rowSum = rowMappings.reduce(
                              (acc, m) => acc + Number(m.weight || 0),
                              0,
                            );
                            return (
                              <TableRow key={assessment.id}>
                                <th
                                  scope="row"
                                  className="p-2.5 text-left text-xs font-medium whitespace-nowrap"
                                >
                                  <span className="tabular-mono">
                                    {assessment.code}
                                  </span>{' '}
                                  <span className="text-muted-foreground">
                                    ({assessment.kind}, max{' '}
                                    {assessment.max_points})
                                  </span>
                                </th>
                                {activeSyllabus.learning_outcomes.map((lo) => {
                                  const cell = rowMappings.find(
                                    (m) => m.learning_outcome === lo.id,
                                  );
                                  return (
                                    <TableCell
                                      key={lo.id}
                                      className="tabular-mono text-right text-xs"
                                    >
                                      {cell ? cell.weight : '—'}
                                    </TableCell>
                                  );
                                })}
                                <TableCell className="tabular-mono text-right text-xs font-semibold">
                                  {rowSum.toFixed(2)}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </section>

                  {/* LO×PO Matrix Preview */}
                  <section className="space-y-2">
                    <h4 className="text-sm font-semibold">
                      Learning Outcome × Program Outcome (LO×PO) matrix preview
                    </h4>
                    <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                      <Table>
                        <TableCaption className="pb-2">
                          LO×PO mapping weights (1–5) for syllabus v
                          {activeSyllabus.version}.
                        </TableCaption>
                        <TableHeader className="bg-[var(--surface-subtle)]">
                          <TableRow>
                            <TableHead scope="col">Learning outcome</TableHead>
                            {programOutcomes.map((po) => (
                              <TableHead
                                key={po.id}
                                scope="col"
                                className="tabular-mono text-center"
                                title={po.label}
                              >
                                {po.code}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {activeSyllabus.learning_outcomes.map((lo) => {
                            const rowMappings = (
                              activeSyllabus.lo_po_mappings ?? []
                            ).filter(
                              (m) =>
                                m.learning_outcome === lo.id && m.is_active,
                            );
                            return (
                              <TableRow key={lo.id}>
                                <th
                                  scope="row"
                                  className="p-2.5 text-left text-xs font-medium"
                                >
                                  <span className="tabular-mono">
                                    {lo.code}
                                  </span>
                                  <span className="block max-w-[220px] truncate font-normal text-muted-foreground">
                                    {lo.description}
                                  </span>
                                </th>
                                {programOutcomes.map((po) => {
                                  const cell = rowMappings.find(
                                    (m) => m.program_outcome === po.id,
                                  );
                                  return (
                                    <TableCell
                                      key={po.id}
                                      className="tabular-mono text-center text-xs"
                                    >
                                      {cell ? (
                                        <span className="inline-flex size-6 items-center justify-center rounded-[4px] bg-[var(--accent-soft)] font-semibold text-[var(--accent-primary)]">
                                          {cell.weight}
                                        </span>
                                      ) : (
                                        <span className="text-muted-foreground">
                                          —
                                        </span>
                                      )}
                                    </TableCell>
                                  );
                                })}
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  </section>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 2: Editable Course -> PO 1-5 Relevance Weights Matrix (CUR-03) */}
      <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
        <CardHeader className="border-b border-border/70 pb-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>
                <h2 className="text-lg font-semibold tracking-tight">
                  Course → PO 1–5 relevance weights matrix
                </h2>
              </CardTitle>
              <CardDescription>
                Configure integer 1–5 relevance weights for courses linked to
                this program (M:N program associations supported). Leave blank
                to clear a weight on a draft syllabus.
              </CardDescription>
            </div>
            {matrixFeedback && (
              <p
                role="status"
                className="text-xs font-medium text-[var(--status-success-fg)]"
              >
                {matrixFeedback}
              </p>
            )}
          </div>
        </CardHeader>

        <CardContent className="space-y-4 pt-5">
          {saveWeightMutation.isError && (
            <Alert variant="destructive">
              <AlertTitle>Unable to save relevance weight</AlertTitle>
              <AlertDescription>
                {errorMessage(saveWeightMutation.error)}
              </AlertDescription>
            </Alert>
          )}

          {Object.values(weightErrors).length > 0 && (
            <Alert variant="destructive">
              <AlertTitle>Invalid relevance weight</AlertTitle>
              <AlertDescription>
                {Object.values(weightErrors)[0]}
              </AlertDescription>
            </Alert>
          )}

          {programOutcomes.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No active PO set found</EmptyTitle>
                <EmptyDescription>
                  Activate a PO1–PO11 set before assigning Course→PO relevance
                  weights.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : coursePoRows.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No courses linked to this program</EmptyTitle>
                <EmptyDescription>
                  Link courses to this program in the academic catalog to
                  configure Course→PO relevance weights.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
              <Table>
                <TableCaption className="pb-3">
                  Course→PO 1–5 relevance weights for courses linked to the
                  selected program. Draft syllabi are editable; approved syllabi
                  are locked.
                </TableCaption>
                <TableHeader className="bg-[var(--surface-subtle)]">
                  <TableRow>
                    <TableHead scope="col">Course</TableHead>
                    <TableHead scope="col">Syllabus</TableHead>
                    {programOutcomes.map((po) => (
                      <TableHead
                        key={po.id}
                        scope="col"
                        className="tabular-mono text-center"
                        title={po.label}
                      >
                        {po.code}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {coursePoRows.map((row) => {
                    const isDraft = row.syllabus?.status === 'draft';
                    return (
                      <TableRow key={row.courseId}>
                        <th
                          scope="row"
                          className="p-2.5 text-left align-middle font-medium"
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="tabular-mono font-semibold">
                              {row.code}
                            </span>
                            {row.linkedPrograms.length > 1 && (
                              <Badge
                                variant="outline"
                                className="text-[10px]"
                                title={`Linked to ${row.linkedPrograms.join(', ')}`}
                              >
                                {row.linkedPrograms.length} programs
                              </Badge>
                            )}
                          </div>
                          <span className="block max-w-[200px] truncate text-xs font-normal text-muted-foreground">
                            {row.title}
                          </span>
                        </th>
                        <TableCell className="whitespace-nowrap text-xs">
                          {row.syllabus ? (
                            <div className="space-y-0.5">
                              <span className="tabular-mono font-medium">
                                v{row.syllabus.version}
                              </span>
                              <div>{statusBadge(row.syllabus.status)}</div>
                            </div>
                          ) : (
                            <NotAssessedText label="— No syllabus" />
                          )}
                        </TableCell>
                        {programOutcomes.map((po) => {
                          const existing = row.contributionsByPo.get(po.id);
                          const syllabusId = row.syllabus?.id ?? '';
                          const cellKey = `${syllabusId}:${po.id}`;
                          const draftValue =
                            weightDrafts[cellKey] ??
                            (existing ? String(existing.weight) : '');
                          const cellError = weightErrors[cellKey];
                          const poCode = poById.get(po.id)?.code ?? po.code;

                          return (
                            <TableCell
                              key={po.id}
                              className="p-1.5 text-center align-middle"
                            >
                              {isDraft && row.syllabus ? (
                                <Input
                                  aria-label={`${row.code} ${poCode} relevance weight (1–5)`}
                                  aria-invalid={Boolean(cellError)}
                                  inputMode="numeric"
                                  maxLength={1}
                                  placeholder="—"
                                  value={draftValue}
                                  disabled={saveWeightMutation.isPending}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    setWeightDrafts((prev) => ({
                                      ...prev,
                                      [cellKey]: val,
                                    }));
                                    const check =
                                      validateCoursePoRelevanceWeight(val);
                                    setWeightErrors((prev) => {
                                      const next = { ...prev };
                                      if (check.ok) delete next[cellKey];
                                      else next[cellKey] = check.error;
                                      return next;
                                    });
                                  }}
                                  onBlur={() =>
                                    handleWeightBlur(
                                      row.syllabus!.id,
                                      po.id,
                                      existing,
                                    )
                                  }
                                  className="tabular-mono mx-auto h-8 w-11 px-1 text-center text-xs"
                                />
                              ) : existing ? (
                                <span
                                  title="Approved syllabus — locked"
                                  className="tabular-mono inline-flex size-7 items-center justify-center rounded-[4px] border border-border bg-muted/60 text-xs font-semibold text-foreground"
                                >
                                  {existing.weight}
                                </span>
                              ) : (
                                <span className="text-xs text-muted-foreground">
                                  —
                                </span>
                              )}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Immutability Confirmation Dialog for Approve & Lock */}
      <Dialog open={confirmApproveOpen} onOpenChange={setConfirmApproveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve and permanently lock syllabus?</DialogTitle>
            <DialogDescription>
              Approving{' '}
              <strong>
                {activeSyllabus
                  ? `${offeringById.get(activeSyllabus.offering)?.label ?? 'Syllabus'} v${activeSyllabus.version}`
                  : 'this syllabus'}
              </strong>{' '}
              permanently locks its learning outcomes, assessments, A×LO
              mappings, LO×PO mappings, and Course→PO relevance weights. Any
              future edits will require creating a new draft revision.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmApproveOpen(false)}
              disabled={approveMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!activeSyllabus || approveMutation.isPending}
              onClick={() =>
                activeSyllabus && approveMutation.mutate(activeSyllabus.id)
              }
            >
              {approveMutation.isPending
                ? 'Locking…'
                : 'Confirm approve & lock'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
