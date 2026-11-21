'use client';

import { useQuery } from '@tanstack/react-query';
import { useId, useMemo } from 'react';
import {
  Badge,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
  Skeleton,
} from '@outcometrik/ui';
import { AcademicQuery } from '../academic-query';
import { useCoordinatorProgramScope } from '../workspace/use-coordinator-program-scope';
import {
  getAllSyllabi,
  getProgramOutcomes,
  type ProgramOutcome,
} from './api';
import { CoursePoWeightsMatrix } from './approvals/course-po-weights-matrix';
import { SyllabusApprovalQueue } from './approvals/syllabus-approval-queue';
import {
  validateCoursePoRelevanceWeight,
  type RelevanceWeightValidation,
} from './approvals/validation';

export { validateCoursePoRelevanceWeight, type RelevanceWeightValidation };

export function CoordinatorApprovalsPanel() {
  const programSelectId = useId();
  const {
    workspaceQuery,
    programs,
    offerings,
    activeProgramId,
    setSelectedProgramId,
    activePoSet,
  } = useCoordinatorProgramScope();

  const syllabiQuery = useQuery({
    queryKey: ['academic', 'syllabi', 'all'],
    queryFn: ({ signal }) => getAllSyllabi(undefined, signal),
    enabled: Boolean(workspaceQuery.data),
  });

  const outcomesQuery = useQuery({
    queryKey: ['academic', 'po-set-outcomes', activePoSet?.id ?? null],
    queryFn: ({ signal }) => getProgramOutcomes(activePoSet?.id ?? '', signal),
    enabled: Boolean(activePoSet?.id),
  });

  const programOutcomes: ProgramOutcome[] = useMemo(
    () => [...(outcomesQuery.data ?? [])].sort((a, b) => a.order - b.order),
    [outcomesQuery.data],
  );

  const offeringById = useMemo(
    () =>
      new Map(
        offerings
          .filter((o) => o.program_id === activeProgramId)
          .map((o) => [o.id, o]),
      ),
    [offerings, activeProgramId],
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

  const draftCount = programSyllabi.filter((s) => s.status === 'draft').length;
  const approvedCount = programSyllabi.filter(
    (s) => s.status === 'approved',
  ).length;

  return (
    <AcademicQuery
      query={workspaceQuery}
      isEmpty={(ws) => ws.programs.length === 0}
    >
      <AcademicQuery.Loading>
        <div className="space-y-4" role="status">
          <p className="text-sm text-muted-foreground">
            Loading syllabus approval queue…
          </p>
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AcademicQuery.Loading>

      <AcademicQuery.Error title="Unable to load coordinator approvals" />

      <AcademicQuery.Empty>
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No authorized programs</EmptyTitle>
            <EmptyDescription>
              You do not have coordinator approval access for any active program.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </AcademicQuery.Empty>

      <AcademicQuery.Ready>
        <div className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)]">
            <Field className="min-w-[260px] max-w-md flex-1">
              <FieldLabel htmlFor={programSelectId}>Program scope</FieldLabel>
              <NativeSelect
                id={programSelectId}
                value={activeProgramId}
                onChange={(e) => setSelectedProgramId(e.target.value)}
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

          <SyllabusApprovalQueue
            key={`queue-${activeProgramId}`}
            syllabiQuery={syllabiQuery}
            syllabi={programSyllabi}
            offeringById={offeringById}
            programOutcomes={programOutcomes}
          />

          <CoursePoWeightsMatrix
            key={`weights-${activeProgramId}`}
            programId={activeProgramId}
            programs={programs}
            programSyllabi={programSyllabi}
            programOutcomes={programOutcomes}
          />
        </div>
      </AcademicQuery.Ready>
    </AcademicQuery>
  );
}
