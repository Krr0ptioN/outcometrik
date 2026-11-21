'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Input,
  NotAssessedText,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import { getCatalogRows } from '../../catalog/api';
import {
  deleteSyllabusPOContribution,
  saveSyllabusPOContribution,
  type CoursePOContribution,
  type ProgramOutcome,
  type Syllabus,
} from '../api';
import { SyllabusStatusDot, validateCoursePoRelevanceWeight } from './validation';

export interface CoursePoWeightsMatrixProps {
  programId: string;
  programs: Array<{ id: string; label: string }>;
  programSyllabi: Syllabus[];
  programOutcomes: ProgramOutcome[];
}

/**
 * Isolated M:N-aware Course -> PO 1-5 Relevance Weights Matrix.
 * Owns its own draft cell state, inline validation, and save mutation so
 * editing weights never re-renders the syllabus approval queue.
 */
export function CoursePoWeightsMatrix({
  programId,
  programs,
  programSyllabi,
  programOutcomes,
}: CoursePoWeightsMatrixProps) {
  const queryClient = useQueryClient();
  const [weightDrafts, setWeightDrafts] = useState<Record<string, string>>({});
  const [weightErrors, setWeightErrors] = useState<Record<string, string>>({});
  const [matrixFeedback, setMatrixFeedback] = useState<string | null>(null);

  const programCoursesQuery = useQuery({
    queryKey: ['academic', 'program-courses', 'all'],
    queryFn: ({ signal }) => getCatalogRows('program-courses', {}, signal),
    enabled: Boolean(programId),
  });

  const coursesQuery = useQuery({
    queryKey: ['academic', 'courses', 'all'],
    queryFn: ({ signal }) => getCatalogRows('courses', {}, signal),
    enabled: Boolean(programId),
  });

  const offeringsQuery = useQuery({
    queryKey: ['academic', 'offerings', programId],
    queryFn: ({ signal }) =>
      getCatalogRows('offerings', { program: programId }, signal),
    enabled: Boolean(programId),
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

  const poById = useMemo(
    () => new Map(programOutcomes.map((po) => [po.id, po])),
    [programOutcomes],
  );

  const coursePoRows = useMemo(() => {
    const allLinks = programCoursesQuery.data ?? [];
    const allCourses = coursesQuery.data ?? [];
    const rawOfferings = offeringsQuery.data ?? [];
    const courseById = new Map(allCourses.map((c) => [c.id, c]));
    const programLabelById = new Map(programs.map((p) => [p.id, p.label]));

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
          .filter((link) => String(link.program ?? '') === programId)
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

      const matchingOfferingIds = rawOfferings
        .filter((o) => String(o.course ?? '') === courseId)
        .map((o) => o.id);

      const courseSyllabi = matchingOfferingIds.flatMap(
        (oid) => syllabiByOffering.get(oid) ?? [],
      );
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
    programId,
    programSyllabi,
  ]);

  const handleWeightBlur = useCallback(
    (
      syllabusId: string,
      programOutcomeId: string,
      existing?: CoursePOContribution,
    ) => {
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
    },
    [weightDrafts, saveWeightMutation],
  );

  const firstWeightError = Object.values(weightErrors)[0];

  return (
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
              Configure integer 1–5 relevance weights for courses linked to this
              program (M:N program associations supported). Leave blank to clear
              a weight on a draft syllabus.
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

        {firstWeightError && (
          <Alert variant="destructive">
            <AlertTitle>Invalid relevance weight</AlertTitle>
            <AlertDescription>{firstWeightError}</AlertDescription>
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
                            <div>
                              <SyllabusStatusDot status={row.syllabus.status} />
                            </div>
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
  );
}
