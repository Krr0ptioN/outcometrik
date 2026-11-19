'use client';

import {
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@outcometrik/api';
import { errorMessage, SessionMenu, useSession } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Field,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import {
  correctGrade,
  createGrade,
  createGradeBatch,
  getApprovedAssessments,
  getGradeBatches,
  getGradeHistory,
  getGrades,
  getReleasedStudentGrades,
  releaseGradeBatch,
  saveGradesBulk,
  type ApprovedAssessment,
  type GradeBatch,
  type GradeBulkItemWrite,
  type GradeCorrection,
  type GradeRecord,
  type GradeState,
  type GradeWrite,
} from './api';
import { getInstructorWorkspace, getStudentWorkspace } from '../workspace/api';

const gradeStates: { value: GradeState; label: string }[] = [
  { value: 'scored', label: 'Scored' },
  { value: 'missing', label: 'Missing' },
  { value: 'exempt', label: 'Exempt' },
  { value: 'withdrawn', label: 'Withdrawn' },
  { value: 'incomplete', label: 'Incomplete' },
];

export function stateLabel(state: GradeState) {
  return gradeStates.find((item) => item.value === state)?.label ?? state;
}

function hasRole(session: ReturnType<typeof useSession>, role: string) {
  return Boolean(
    session.data?.roles.some((assignment) => assignment.role === role),
  );
}

function AccessMessage({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-svh max-w-4xl flex-col gap-4 p-8">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <SessionMenu />
      </header>
      {children}
    </main>
  );
}

export type GradeDraft = {
  state: GradeState;
  points: string;
  reason: string;
};

export type CellValidationResult = {
  valid: boolean;
  error: string | null;
};

export function validateGradeDraft({
  draft,
  scoreLimit,
  reasonRequired,
}: {
  draft: GradeDraft;
  scoreLimit: string;
  reasonRequired: boolean;
}): CellValidationResult {
  const limit = Number(scoreLimit);
  if (draft.state === 'scored') {
    const raw = draft.points.trim();
    if (!raw) {
      return {
        valid: false,
        error: `Points earned are required when scored (0 to ${scoreLimit}).`,
      };
    }
    const num = Number(raw);
    if (!Number.isFinite(num) || Number.isNaN(num)) {
      return {
        valid: false,
        error: 'Points earned must be a valid decimal number.',
      };
    }
    if (num < 0 || num > limit) {
      return {
        valid: false,
        error: `Points earned must be between 0 and ${scoreLimit}.`,
      };
    }
  } else if (draft.points.trim() !== '') {
    return {
      valid: false,
      error: 'Points earned must be empty unless the grade state is Scored.',
    };
  }

  if (reasonRequired && !draft.reason.trim()) {
    return {
      valid: false,
      error: 'A reason is required for grades in a released batch.',
    };
  }

  return { valid: true, error: null };
}

export function isDraftDirty(
  draft: GradeDraft | undefined,
  grade: GradeRecord | undefined,
): boolean {
  if (!draft) return false;
  if (!grade) {
    return (
      draft.state !== 'scored' ||
      draft.points.trim() !== '' ||
      draft.reason.trim() !== ''
    );
  }
  const existingPoints = grade.points_earned ?? '';
  if (draft.state !== grade.state) return true;
  if (draft.state === 'scored') {
    if (draft.points.trim() === '') return true;
    return Number(draft.points) !== Number(existingPoints);
  }
  return false;
}

export function sortRosterDeterministically<
  T extends { enrollment_id: string; name: string; status: string },
>(roster: readonly T[]): T[] {
  return [...roster].sort((a, b) => {
    const byName = a.name.localeCompare(b.name, 'en', {
      sensitivity: 'base',
    });
    if (byName !== 0) return byName;
    return a.enrollment_id.localeCompare(b.enrollment_id);
  });
}

export function paginateRoster<T>(
  rows: readonly T[],
  page: number,
  pageSize: number,
): {
  items: T[];
  currentPage: number;
  totalPages: number;
  totalItems: number;
} {
  const safeSize = Math.max(1, pageSize);
  const totalItems = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / safeSize));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  const start = (currentPage - 1) * safeSize;
  return {
    items: rows.slice(start, start + safeSize),
    currentPage,
    totalPages,
    totalItems,
  };
}

export function computeNextGridCell(
  rowIndex: number,
  colIndex: number,
  rowCount: number,
  colCount: number,
  key: string,
): { rowIndex: number; colIndex: number } | null {
  if (rowCount <= 0 || colCount <= 0) return null;
  if (key === 'ArrowDown') {
    return {
      rowIndex: Math.min(rowCount - 1, rowIndex + 1),
      colIndex,
    };
  }
  if (key === 'ArrowUp') {
    return {
      rowIndex: Math.max(0, rowIndex - 1),
      colIndex,
    };
  }
  if (key === 'ArrowRight') {
    return {
      rowIndex,
      colIndex: Math.min(colCount - 1, colIndex + 1),
    };
  }
  if (key === 'ArrowLeft') {
    return {
      rowIndex,
      colIndex: Math.max(0, colIndex - 1),
    };
  }
  return null;
}

function makeIdempotencyKey(offeringId: string) {
  const randomPart =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  return `gradebook-${offeringId}-${randomPart}`;
}

function GradeMatrixCell({
  enrollmentId,
  studentName,
  enrollmentStatus,
  assessment,
  rowIndex,
  colIndex,
  rowCount,
  colCount,
  batch,
  grade,
  draftOverlay,
  cellError,
  onDraftChange,
  onDiscardDraft,
  onSaveCell,
  writesPending,
}: {
  enrollmentId: string;
  studentName: string;
  enrollmentStatus: string;
  assessment: ApprovedAssessment;
  rowIndex: number;
  colIndex: number;
  rowCount: number;
  colCount: number;
  batch: GradeBatch | undefined;
  grade: GradeRecord | undefined;
  draftOverlay: GradeDraft | undefined;
  cellError: string | null;
  onDraftChange: (cellKey: string, nextDraft: GradeDraft) => void;
  onDiscardDraft: (cellKey: string) => void;
  onSaveCell: (params: {
    cellKey: string;
    grade: GradeRecord | undefined;
    draft: GradeDraft;
    enrollmentId: string;
    assessment: ApprovedAssessment;
    batch: GradeBatch | undefined;
    studentName: string;
  }) => Promise<unknown>;
  writesPending: boolean;
}) {
  const cellKey = `${enrollmentId}:${assessment.id}`;
  const defaultDraft: GradeDraft = {
    state: grade?.state ?? 'scored',
    points: grade?.points_earned ?? '',
    reason: '',
  };
  const draft = draftOverlay ?? defaultDraft;
  const { state, points, reason } = draft;
  const [showHistory, setShowHistory] = useState(false);

  const history = useQuery({
    queryKey: ['academic', 'grade-history', grade?.id],
    queryFn: ({ signal }) => getGradeHistory(grade!.id, signal),
    enabled: Boolean(grade && showHistory),
  });

  const save = useMutation({
    mutationFn: () =>
      onSaveCell({
        cellKey,
        grade,
        draft,
        enrollmentId,
        assessment,
        batch,
        studentName,
      }),
  });

  const scoreLimit = grade?.points_possible ?? assessment.points_possible;
  const batchIsReleased = Boolean(batch?.released_at);
  const correctionIsReleased = grade?.batch === batch?.id && batchIsReleased;
  const reasonRequired = Boolean(
    grade ? correctionIsReleased : batchIsReleased,
  );
  const canSave =
    enrollmentStatus === 'enrolled' && (Boolean(grade) || Boolean(batch));
  const dirty = isDraftDirty(draftOverlay, grade);

  function updateDraft(patch: Partial<GradeDraft>) {
    save.reset();
    onDraftChange(cellKey, { ...draft, ...patch });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate();
  }

  function handleCellKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape' && draftOverlay) {
      event.preventDefault();
      save.reset();
      onDiscardDraft(cellKey);
      return;
    }
    if (event.altKey || event.ctrlKey) {
      const next = computeNextGridCell(
        rowIndex,
        colIndex,
        rowCount,
        colCount,
        event.key,
      );
      if (next && typeof document !== 'undefined') {
        event.preventDefault();
        const target = document.querySelector<HTMLElement>(
          `[data-grid-focus="${next.rowIndex}-${next.colIndex}"]`,
        );
        target?.focus();
      }
    }
  }

  const inputIdSuffix = `${enrollmentId}-${assessment.id}`;
  const isInvalid = Boolean(cellError);

  return (
    <TableCell
      data-grid-cell={`${rowIndex}-${colIndex}`}
      className={`min-w-72 align-top ${
        isInvalid ? 'bg-destructive/5 ring-1 ring-destructive/40' : ''
      }`}
    >
      <div className="space-y-3">
        <div className="space-y-1.5 rounded-md border bg-muted/20 p-2.5">
          <div className="flex flex-wrap items-center justify-between gap-1.5">
            {grade ? (
              <span className="text-sm font-medium">
                {stateLabel(grade.state)}
                {grade.state === 'scored' && (
                  <span className="ml-1.5">
                    {grade.points_earned} / {grade.points_possible}
                  </span>
                )}
              </span>
            ) : (
              <span className="text-sm text-muted-foreground">Not entered</span>
            )}
            <div className="flex flex-wrap items-center gap-1">
              {grade?.state === 'scored' &&
                Number(grade.points_earned) === 0 && (
                  <Badge variant="secondary">Recorded zero</Badge>
                )}
              {grade?.state === 'missing' && (
                <Badge variant="secondary">Missing</Badge>
              )}
              {grade?.state === 'exempt' && (
                <Badge variant="outline">Exempt</Badge>
              )}
              {(grade?.state === 'withdrawn' ||
                enrollmentStatus === 'withdrawn') && (
                <Badge variant="secondary">Withdrawn</Badge>
              )}
              {grade?.state === 'incomplete' && (
                <Badge variant="secondary">Incomplete</Badge>
              )}
              {batch && (
                <Badge variant={batchIsReleased ? 'default' : 'outline'}>
                  {batchIsReleased ? 'Released' : 'Unreleased (draft)'}
                </Badge>
              )}
              {dirty && <Badge variant="secondary">Unsaved draft</Badge>}
              {isInvalid && <Badge variant="destructive">Invalid</Badge>}
            </div>
          </div>
          {grade && (
            <p className="text-xs text-muted-foreground">
              {grade.batch_name} · version {grade.version}
            </p>
          )}
        </div>

        <form onSubmit={submit} className="space-y-2.5" noValidate>
          <Field>
            <FieldLabel htmlFor={`state-${inputIdSuffix}`}>
              Grade state for {studentName} ({assessment.title})
            </FieldLabel>
            <NativeSelect
              id={`state-${inputIdSuffix}`}
              data-grid-focus={`${rowIndex}-${colIndex}`}
              value={state}
              onKeyDown={handleCellKeyDown}
              onChange={(event) =>
                updateDraft({ state: event.target.value as GradeState })
              }
              disabled={!canSave || save.isPending || writesPending}
              aria-invalid={isInvalid}
            >
              {gradeStates.map((item) => (
                <NativeSelectOption key={item.value} value={item.value}>
                  {item.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>

          {state === 'scored' && (
            <Field>
              <FieldLabel htmlFor={`points-${inputIdSuffix}`}>
                Points earned for {studentName} (out of {scoreLimit})
              </FieldLabel>
              <Input
                id={`points-${inputIdSuffix}`}
                type="number"
                inputMode="decimal"
                min="0"
                max={scoreLimit}
                step="0.01"
                required
                value={points}
                onKeyDown={handleCellKeyDown}
                onChange={(event) =>
                  updateDraft({ points: event.target.value })
                }
                disabled={!canSave || save.isPending || writesPending}
                aria-invalid={isInvalid}
                aria-describedby={`points-help-${inputIdSuffix}`}
              />
              <p
                id={`points-help-${inputIdSuffix}`}
                className="text-xs text-muted-foreground"
              >
                Enter 0 for a recorded zero (0 / {scoreLimit}). Missing is never
                converted to zero.
              </p>
            </Field>
          )}

          {reasonRequired && (
            <Field>
              <FieldLabel htmlFor={`reason-${inputIdSuffix}`}>
                {grade
                  ? `Correction reason for ${studentName}`
                  : `Reason for entering a released grade for ${studentName}`}
              </FieldLabel>
              <Input
                id={`reason-${inputIdSuffix}`}
                value={reason}
                onKeyDown={handleCellKeyDown}
                onChange={(event) =>
                  updateDraft({ reason: event.target.value })
                }
                maxLength={255}
                required
                disabled={!canSave || save.isPending || writesPending}
                aria-invalid={isInvalid}
                aria-describedby={`reason-help-${inputIdSuffix}`}
              />
              <p
                id={`reason-help-${inputIdSuffix}`}
                className="text-xs text-muted-foreground"
              >
                A reason is recorded in the grade history because this batch has
                been released.
              </p>
            </Field>
          )}

          {cellError && (
            <p
              id={`error-${inputIdSuffix}`}
              role="alert"
              className="text-xs font-medium text-destructive"
            >
              {cellError}
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              size="sm"
              disabled={!canSave || save.isPending || writesPending}
            >
              {save.isPending
                ? 'Saving…'
                : grade
                  ? 'Save correction'
                  : 'Save grade'}
            </Button>
            {dirty && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  save.reset();
                  onDiscardDraft(cellKey);
                }}
                disabled={save.isPending || writesPending}
              >
                Reset
              </Button>
            )}
            {grade && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setShowHistory((current) => !current)}
                aria-expanded={showHistory}
              >
                {showHistory ? 'Hide history' : 'History'}
              </Button>
            )}
          </div>

          {enrollmentStatus !== 'enrolled' && (
            <p className="text-xs text-muted-foreground">
              Only actively enrolled students can receive a grade.
            </p>
          )}

          {save.isError && !cellError && (
            <p role="alert" className="text-xs text-destructive">
              {save.error instanceof ApiError && save.error.kind === 'conflict'
                ? 'This grade changed while you were editing it. Refresh latest grades and review before saving again.'
                : errorMessage(save.error)}
            </p>
          )}

          {showHistory && (
            <div className="border-l pl-3 text-xs">
              {history.isPending && (
                <p role="status">Loading change history…</p>
              )}
              {history.isError && (
                <p role="alert">{errorMessage(history.error)}</p>
              )}
              {history.data?.map((entry) => (
                <p key={entry.version} className="py-1">
                  v{entry.version} · {stateLabel(entry.new_state)}
                  {entry.new_state === 'scored' &&
                    ` · ${entry.new_points_earned} points`}
                  {entry.reason && ` · ${entry.reason}`}
                  <span className="block text-muted-foreground">
                    {new Date(entry.created_at).toLocaleString()}
                  </span>
                </p>
              ))}
            </div>
          )}
        </form>
      </div>
    </TableCell>
  );
}

export function InstructorGradebook({
  embedded = false,
  defaultOfferingId = '',
}: {
  embedded?: boolean;
  defaultOfferingId?: string;
} = {}) {
  const session = useSession();
  const allowed = hasRole(session, 'instructor');
  const queryClient = useQueryClient();
  const workspace = useQuery({
    queryKey: ['academic', 'instructor'],
    queryFn: ({ signal }) => getInstructorWorkspace(signal),
    enabled: allowed,
  });
  const [selectedOffering, setSelectedOffering] = useState(defaultOfferingId);
  const offerings = workspace.data?.offerings ?? [];
  const offeringId = offerings.some((item) => item.id === selectedOffering)
    ? selectedOffering
    : (offerings[0]?.id ?? '');
  const board = useQuery({
    queryKey: ['academic', 'gradebook', offeringId],
    queryFn: async ({ signal }) => {
      const [assessments, batches, grades] = await Promise.all([
        getApprovedAssessments(offeringId, signal),
        getGradeBatches(offeringId, signal),
        getGrades(offeringId, signal),
      ]);
      return { assessments, batches, grades };
    },
    enabled: allowed && Boolean(offeringId),
  });
  const [assessmentChoice, setAssessmentChoice] = useState('__all__');
  const [batchChoice, setBatchChoice] = useState('');
  const [batchName, setBatchName] = useState('');
  const [studentSearch, setStudentSearch] = useState('');
  const [gradeFilter, setGradeFilter] = useState<
    'all' | 'graded' | 'needs-grade'
  >('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [drafts, setDrafts] = useState<Record<string, GradeDraft>>({});
  const [cellErrors, setCellErrors] = useState<Record<string, string>>({});
  const [gradeSaveMessage, setGradeSaveMessage] = useState('');
  const [conflictAlertMessage, setConflictAlertMessage] = useState('');
  const [confirmRelease, setConfirmRelease] = useState(false);

  const active = board.data;
  const assessments = active?.assessments ?? [];
  const batches = active?.batches ?? [];

  const visibleAssessments =
    assessmentChoice === '__all__' ||
    !assessments.some((item) => item.id === assessmentChoice)
      ? assessments
      : assessments.filter((item) => item.id === assessmentChoice);

  const chosenBatch =
    batches.find((item) => item.id === batchChoice) ?? batches[0];
  const selectedBatch =
    batches.find((item) => item.id === batchChoice) ?? chosenBatch;
  const selectedOfferingData = offerings.find((item) => item.id === offeringId);
  const sortedRoster = sortRosterDeterministically(
    selectedOfferingData?.roster ?? [],
  );

  const gradesByCell = new Map(
    (active?.grades ?? []).map((grade) => [
      `${grade.enrollment}:${grade.assessment}`,
      grade,
    ]),
  );

  const isStudentFullyGraded = (enrollmentId: string) =>
    visibleAssessments.length > 0 &&
    visibleAssessments.every((asmt) =>
      gradesByCell.has(`${enrollmentId}:${asmt.id}`),
    );

  const isStudentAnyGraded = (enrollmentId: string) =>
    visibleAssessments.some((asmt) =>
      gradesByCell.has(`${enrollmentId}:${asmt.id}`),
    );

  const gradedCount = sortedRoster.filter((student) =>
    isStudentAnyGraded(student.enrollment_id),
  ).length;
  const needsGradeCount = sortedRoster.filter(
    (student) =>
      student.status === 'enrolled' &&
      !isStudentFullyGraded(student.enrollment_id),
  ).length;

  const filteredRoster = sortedRoster.filter((student) => {
    const matchesSearch = student.name
      .toLocaleLowerCase()
      .includes(studentSearch.trim().toLocaleLowerCase());
    if (!matchesSearch) return false;
    if (gradeFilter === 'graded') {
      return isStudentAnyGraded(student.enrollment_id);
    }
    if (gradeFilter === 'needs-grade') {
      return (
        student.status === 'enrolled' &&
        !isStudentFullyGraded(student.enrollment_id)
      );
    }
    return true;
  });

  const pagination = paginateRoster(filteredRoster, page, pageSize);
  const visibleRoster = pagination.items;

  const boardKey = ['academic', 'gradebook', offeringId] as const;
  const workspaceKey = ['academic', 'instructor'] as const;

  const dirtyCellKeys = Object.keys(drafts).filter((key) =>
    isDraftDirty(drafts[key], gradesByCell.get(key)),
  );

  function setCellDraft(cellKey: string, nextDraft: GradeDraft) {
    setDrafts((prev) => ({ ...prev, [cellKey]: nextDraft }));
    setCellErrors((prev) => {
      if (!(cellKey in prev)) return prev;
      const copy = { ...prev };
      delete copy[cellKey];
      return copy;
    });
  }

  function discardCellDraft(cellKey: string) {
    setDrafts((prev) => {
      if (!(cellKey in prev)) return prev;
      const copy = { ...prev };
      delete copy[cellKey];
      return copy;
    });
    setCellErrors((prev) => {
      if (!(cellKey in prev)) return prev;
      const copy = { ...prev };
      delete copy[cellKey];
      return copy;
    });
  }

  async function refreshLatestGrades() {
    setConflictAlertMessage('');
    setGradeSaveMessage('Refreshed latest grades from server.');
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: boardKey }),
      queryClient.invalidateQueries({ queryKey: workspaceKey }),
    ]);
  }

  const saveGrade = useMutation({
    mutationFn: async (input: {
      cellKey: string;
      grade: GradeRecord | undefined;
      draft: GradeDraft;
      enrollmentId: string;
      assessment: ApprovedAssessment;
      batch: GradeBatch | undefined;
      studentName: string;
    }) => {
      const scoreLimit =
        input.grade?.points_possible ?? input.assessment.points_possible;
      const batchIsReleased = Boolean(input.batch?.released_at);
      const correctionIsReleased =
        input.grade?.batch === input.batch?.id && batchIsReleased;
      const reasonRequired = Boolean(
        input.grade ? correctionIsReleased : batchIsReleased,
      );
      const check = validateGradeDraft({
        draft: input.draft,
        scoreLimit,
        reasonRequired,
      });
      if (!check.valid) {
        setCellErrors((prev) => ({
          ...prev,
          [input.cellKey]: check.error ?? 'Invalid grade value.',
        }));
        throw new Error(check.error ?? 'Invalid grade value.');
      }

      const points =
        input.draft.state === 'scored' ? input.draft.points.trim() : null;
      if (input.grade) {
        const body: GradeCorrection = {
          expected_version: input.grade.version,
          state: input.draft.state,
          points_earned: points,
          reason: input.draft.reason.trim(),
        };
        return correctGrade(input.grade.id, body);
      }
      const body: GradeWrite = {
        enrollment: input.enrollmentId,
        assessment: input.assessment.id,
        batch: input.batch?.id ?? '',
        state: input.draft.state,
        points_earned: points,
        reason: input.draft.reason.trim(),
      };
      return createGrade(body);
    },
    onMutate: () => {
      setGradeSaveMessage('');
      setConflictAlertMessage('');
    },
    onSuccess: async (_, input) => {
      discardCellDraft(input.cellKey);
      const action = input.grade ? 'Grade correction saved' : 'Grade saved';
      setGradeSaveMessage(
        `${action} for ${input.studentName} (${input.assessment.title}).`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: boardKey }),
        queryClient.invalidateQueries({ queryKey: workspaceKey }),
      ]);
    },
    onError: (error, input) => {
      if (error instanceof ApiError && error.kind === 'conflict') {
        const msg = `${input.studentName}'s grade for ${input.assessment.title} changed while you were editing it (HTTP 409 Conflict). Refresh latest grades and review before saving again.`;
        setConflictAlertMessage(msg);
        setGradeSaveMessage(msg);
        void queryClient.invalidateQueries({ queryKey: boardKey });
      }
    },
  });

  const bulkSaveMutation = useMutation({
    mutationFn: async () => {
      if (!dirtyCellKeys.length || !selectedBatch) {
        return null;
      }
      const nextErrors: Record<string, string> = {};
      const items: GradeBulkItemWrite[] = [];

      for (const cellKey of dirtyCellKeys) {
        const [enrollmentId, assessmentId] = cellKey.split(':');
        const asmt = assessments.find((a) => a.id === assessmentId);
        const student = sortedRoster.find(
          (s) => s.enrollment_id === enrollmentId,
        );
        if (!asmt || !student || student.status !== 'enrolled') continue;

        const existing = gradesByCell.get(cellKey);
        const draft = drafts[cellKey];
        if (!draft) continue;

        const targetBatch = existing
          ? batches.find((b) => b.id === existing.batch)
          : selectedBatch;
        const scoreLimit = existing?.points_possible ?? asmt.points_possible;
        const batchIsReleased = Boolean(targetBatch?.released_at);
        const correctionIsReleased =
          existing?.batch === targetBatch?.id && batchIsReleased;
        const reasonRequired = Boolean(
          existing ? correctionIsReleased : batchIsReleased,
        );

        const check = validateGradeDraft({
          draft,
          scoreLimit,
          reasonRequired,
        });
        if (!check.valid) {
          nextErrors[cellKey] =
            `${student.name} (${asmt.title}): ${check.error ?? 'Invalid grade.'}`;
          continue;
        }

        items.push({
          enrollment: enrollmentId,
          assessment: assessmentId,
          batch: existing?.batch ?? selectedBatch.id,
          state: draft.state,
          points_earned: draft.state === 'scored' ? draft.points.trim() : null,
          reason: draft.reason.trim(),
          ...(existing ? { expected_version: existing.version } : {}),
        });
      }

      if (Object.keys(nextErrors).length > 0) {
        setCellErrors((prev) => ({ ...prev, ...nextErrors }));
        throw new Error(
          'Fix validation errors in highlighted cells before bulk saving.',
        );
      }

      return saveGradesBulk({
        offering: offeringId,
        expected_input_revision: selectedOfferingData?.input_revision,
        idempotency_key: makeIdempotencyKey(offeringId),
        items,
      });
    },
    onMutate: () => {
      setGradeSaveMessage('');
      setConflictAlertMessage('');
    },
    onSuccess: async (result) => {
      if (!result) return;
      setDrafts({});
      setCellErrors({});
      setGradeSaveMessage(
        `Saved ${result.grades.length} grade change${result.grades.length === 1 ? '' : 's'} (revision v${result.input_revision}).`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: boardKey }),
        queryClient.invalidateQueries({ queryKey: workspaceKey }),
      ]);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.kind === 'conflict') {
        const msg =
          'Gradebook revision conflict (HTTP 409): one or more grades were modified concurrently. Refresh latest grades and retry your changes.';
        setConflictAlertMessage(msg);
        setGradeSaveMessage(msg);
      }
    },
  });

  const addBatch = useMutation({
    mutationFn: (name: string) => createGradeBatch(offeringId, name),
    onSuccess: async (created) => {
      setBatchName('');
      setBatchChoice(created.id);
      await queryClient.invalidateQueries({ queryKey: boardKey });
    },
  });

  const release = useMutation({
    mutationFn: (batchId: string) => releaseGradeBatch(batchId),
    onSuccess: async () => {
      setConfirmRelease(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: boardKey }),
        queryClient.invalidateQueries({ queryKey: workspaceKey }),
      ]);
    },
  });

  const writesPending =
    saveGrade.isPending ||
    bulkSaveMutation.isPending ||
    addBatch.isPending ||
    release.isPending;

  if (session.isPending || (allowed && workspace.isPending)) {
    return (
      <main className="mx-auto max-w-6xl space-y-4 p-8" role="status">
        <span className="sr-only">Loading gradebook…</span>
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-72 w-full" />
      </main>
    );
  }
  if (!session.data?.user) {
    return (
      <AccessMessage title="Sign in to continue.">
        <a href="/login">Go to sign in →</a>
      </AccessMessage>
    );
  }
  if (!allowed) {
    return (
      <AccessMessage title="Instructor access required.">
        <p>This account has no active instructor role.</p>
      </AccessMessage>
    );
  }
  if (workspace.isError) {
    return (
      <AccessMessage title="Could not load your offerings.">
        <p role="alert">{errorMessage(workspace.error)}</p>
      </AccessMessage>
    );
  }

  function createBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addBatch.mutate(batchName.trim());
  }

  const errorList = Object.entries(cellErrors);
  const Container = embedded ? 'section' : 'main';

  return (
    <Container
      aria-label={embedded ? 'Gradebook operations' : undefined}
      className={
        embedded
          ? 'flex flex-col gap-6'
          : 'mx-auto flex min-h-svh max-w-7xl flex-col gap-6 p-6 md:p-8'
      }
    >
      {!embedded && (
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Teaching workspace</p>
            <h1 className="text-3xl font-semibold">Gradebook</h1>
          </div>
          <SessionMenu />
        </header>
      )}
      {offerings.length === 0 ? (
        <p>No offerings are assigned to this account.</p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Offering and assessment columns</CardTitle>
              <CardDescription>
                View all approved assessments side-by-side in the roster matrix
                or focus on a single assessment column. Zero is a real measured
                score; missing and exempt states remain distinct.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="gradebook-offering">Offering</FieldLabel>
                <NativeSelect
                  id="gradebook-offering"
                  value={offeringId}
                  onChange={(event) => {
                    setGradeSaveMessage('');
                    setConflictAlertMessage('');
                    setConfirmRelease(false);
                    setDrafts({});
                    setCellErrors({});
                    setPage(1);
                    setSelectedOffering(event.target.value);
                  }}
                  disabled={writesPending}
                >
                  {offerings.map((item) => (
                    <NativeSelectOption key={item.id} value={item.id}>
                      {item.label} · {item.course} · {item.term}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              <Field>
                <FieldLabel htmlFor="gradebook-assessment">
                  Approved assessment columns
                </FieldLabel>
                <NativeSelect
                  id="gradebook-assessment"
                  value={assessmentChoice}
                  onChange={(event) => {
                    setGradeSaveMessage('');
                    setAssessmentChoice(event.target.value);
                  }}
                  disabled={
                    !assessments.length || board.isPending || writesPending
                  }
                >
                  {assessments.length ? (
                    <>
                      <NativeSelectOption value="__all__">
                        All approved assessments ({assessments.length})
                      </NativeSelectOption>
                      {assessments.map((item) => (
                        <NativeSelectOption key={item.id} value={item.id}>
                          {item.title} · {item.points_possible} points
                        </NativeSelectOption>
                      ))}
                    </>
                  ) : (
                    <NativeSelectOption value="">
                      No approved assessments
                    </NativeSelectOption>
                  )}
                </NativeSelect>
              </Field>
              {visibleAssessments.length > 0 && (
                <p className="text-sm text-muted-foreground md:col-span-2">
                  {selectedOfferingData?.course} · showing{' '}
                  {visibleAssessments.length} approved assessment
                  {visibleAssessments.length === 1 ? '' : 's'} (
                  {visibleAssessments
                    .map(
                      (a) => `${a.title}: maximum score ${a.points_possible}`,
                    )
                    .join(' · ')}
                  )
                </p>
              )}
            </CardContent>
          </Card>

          {board.isPending && <p role="status">Loading gradebook…</p>}
          {board.isError && <p role="alert">{errorMessage(board.error)}</p>}
          {board.data && !assessments.length && (
            <Alert>
              <AlertDescription>
                No approved assessments are available for this offering. Ask
                your coordinator to finish the syllabus assessment setup before
                entering grades.
              </AlertDescription>
            </Alert>
          )}

          {board.data && assessments.length > 0 && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Grade batch</CardTitle>
                  <CardDescription>
                    Grades are grouped into batches. Releasing a batch makes its
                    grades visible to students; corrections to released grades
                    require a reason.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap items-end gap-3">
                    <Field className="min-w-64 flex-1">
                      <FieldLabel htmlFor="gradebook-batch">
                        Grade batch
                      </FieldLabel>
                      <NativeSelect
                        id="gradebook-batch"
                        value={selectedBatch?.id ?? ''}
                        onChange={(event) => {
                          setConfirmRelease(false);
                          setBatchChoice(event.target.value);
                        }}
                        disabled={!batches.length || writesPending}
                      >
                        {batches.length ? (
                          batches.map((batch) => (
                            <NativeSelectOption key={batch.id} value={batch.id}>
                              {batch.name}
                              {batch.released_at
                                ? ' · Released'
                                : ' · Unreleased (draft)'}
                            </NativeSelectOption>
                          ))
                        ) : (
                          <NativeSelectOption value="">
                            Create a batch to begin
                          </NativeSelectOption>
                        )}
                      </NativeSelect>
                    </Field>
                    {selectedBatch && (
                      <Badge
                        variant={
                          selectedBatch.released_at ? 'default' : 'outline'
                        }
                      >
                        {selectedBatch.released_at
                          ? 'Released batch'
                          : 'Unreleased (draft) batch'}
                      </Badge>
                    )}
                    {selectedBatch && !selectedBatch.released_at && (
                      <Button
                        variant="outline"
                        onClick={() => setConfirmRelease((current) => !current)}
                        disabled={release.isPending}
                      >
                        Release {selectedBatch.name}
                      </Button>
                    )}
                  </div>
                  {confirmRelease && selectedBatch && (
                    <div
                      className="rounded-md border p-4"
                      aria-labelledby="release-warning"
                    >
                      <p id="release-warning" className="font-medium">
                        Students will be able to see released grades in this
                        batch.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          onClick={() => release.mutate(selectedBatch.id)}
                          disabled={writesPending}
                        >
                          {release.isPending ? 'Releasing…' : 'Confirm release'}
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => setConfirmRelease(false)}
                          disabled={writesPending}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                  {release.isError && (
                    <p role="alert">{errorMessage(release.error)}</p>
                  )}
                  <form
                    onSubmit={createBatch}
                    className="flex flex-wrap items-end gap-3"
                  >
                    <Field className="min-w-64 flex-1">
                      <FieldLabel htmlFor="new-grade-batch">
                        New batch name
                      </FieldLabel>
                      <Input
                        id="new-grade-batch"
                        value={batchName}
                        onChange={(event) => setBatchName(event.target.value)}
                        maxLength={120}
                        required
                        disabled={writesPending}
                      />
                    </Field>
                    <Button
                      type="submit"
                      variant="outline"
                      disabled={writesPending || !batchName.trim()}
                    >
                      {addBatch.isPending ? 'Creating…' : 'Create batch'}
                    </Button>
                  </form>
                  {addBatch.isError && (
                    <p role="alert">{errorMessage(addBatch.error)}</p>
                  )}
                </CardContent>
              </Card>

              {selectedBatch &&
                visibleAssessments.length > 0 &&
                selectedOfferingData && (
                  <Card>
                    <CardHeader className="flex flex-wrap items-start justify-between gap-4 sm:flex-row">
                      <div>
                        <CardTitle>
                          {visibleAssessments.length === 1
                            ? `${visibleAssessments[0].title} roster`
                            : 'Roster × assessment gradebook matrix'}
                        </CardTitle>
                        <CardDescription>
                          {selectedOfferingData.label} · {selectedBatch.name} ·{' '}
                          {sortedRoster.length} students ·{' '}
                          {visibleAssessments.length} assessment column
                          {visibleAssessments.length === 1 ? '' : 's'}
                          {selectedOfferingData.input_revision !== undefined &&
                            ` · revision v${selectedOfferingData.input_revision}`}
                        </CardDescription>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">
                          {dirtyCellKeys.length} unsaved cell
                          {dirtyCellKeys.length === 1 ? '' : 's'}
                        </Badge>
                        <Button
                          type="button"
                          onClick={() => bulkSaveMutation.mutate()}
                          disabled={
                            !dirtyCellKeys.length ||
                            writesPending ||
                            !selectedBatch
                          }
                        >
                          {bulkSaveMutation.isPending
                            ? 'Saving changes…'
                            : `Save all changes (${dirtyCellKeys.length})`}
                        </Button>
                        {dirtyCellKeys.length > 0 && (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              setDrafts({});
                              setCellErrors({});
                            }}
                            disabled={writesPending}
                          >
                            Discard drafts
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="mb-5 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-md border p-3">
                          <p className="text-sm text-muted-foreground">
                            Roster
                          </p>
                          <p className="text-2xl font-semibold">
                            {sortedRoster.length}
                          </p>
                        </div>
                        <div className="rounded-md border p-3">
                          <p className="text-sm text-muted-foreground">
                            Grades entered
                          </p>
                          <p className="text-2xl font-semibold">
                            {gradedCount}
                          </p>
                        </div>
                        <div className="rounded-md border p-3">
                          <p className="text-sm text-muted-foreground">
                            Needs a grade
                          </p>
                          <p className="text-2xl font-semibold">
                            {needsGradeCount}
                          </p>
                        </div>
                      </div>

                      <div className="mb-4 grid gap-4 sm:grid-cols-3">
                        <Field>
                          <FieldLabel htmlFor="gradebook-student-search">
                            Find a student
                          </FieldLabel>
                          <Input
                            id="gradebook-student-search"
                            type="search"
                            value={studentSearch}
                            onChange={(event) => {
                              setPage(1);
                              setStudentSearch(event.target.value);
                            }}
                          />
                        </Field>
                        <Field>
                          <FieldLabel htmlFor="gradebook-grade-filter">
                            Show students
                          </FieldLabel>
                          <NativeSelect
                            id="gradebook-grade-filter"
                            value={gradeFilter}
                            onChange={(event) => {
                              setPage(1);
                              setGradeFilter(
                                event.target.value as typeof gradeFilter,
                              );
                            }}
                          >
                            <NativeSelectOption value="all">
                              All students
                            </NativeSelectOption>
                            <NativeSelectOption value="needs-grade">
                              Needs a grade (enrolled)
                            </NativeSelectOption>
                            <NativeSelectOption value="graded">
                              Grade entered
                            </NativeSelectOption>
                          </NativeSelect>
                        </Field>
                        <Field>
                          <FieldLabel htmlFor="gradebook-page-size">
                            Rows per page
                          </FieldLabel>
                          <NativeSelect
                            id="gradebook-page-size"
                            value={String(pageSize)}
                            onChange={(event) => {
                              setPage(1);
                              setPageSize(Number(event.target.value));
                            }}
                          >
                            {[5, 10, 25, 50].map((size) => (
                              <NativeSelectOption
                                key={size}
                                value={String(size)}
                              >
                                {size} students per page
                              </NativeSelectOption>
                            ))}
                          </NativeSelect>
                        </Field>
                      </div>

                      <p className="mb-3 text-xs text-muted-foreground">
                        Keyboard navigation: Use Tab to move between fields,
                        Alt+Arrow keys (or Ctrl+Arrow keys) to jump across
                        student rows and assessment columns, Enter to save a
                        cell, and Escape to reset an unsaved cell draft.
                      </p>

                      {conflictAlertMessage && (
                        <Alert className="mb-4 border-destructive">
                          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                            <span role="alert" className="font-medium">
                              {conflictAlertMessage}
                            </span>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void refreshLatestGrades()}
                            >
                              Refresh latest grades
                            </Button>
                          </AlertDescription>
                        </Alert>
                      )}

                      {errorList.length > 0 && (
                        <Alert className="mb-4 border-destructive">
                          <AlertDescription>
                            <div role="alert" className="space-y-1">
                              <p className="font-medium text-destructive">
                                Grade validation failed ({errorList.length} cell
                                {errorList.length === 1 ? '' : 's'}). Valid
                                drafts remain preserved:
                              </p>
                              <ul className="list-disc pl-5 text-xs text-destructive">
                                {errorList.map(([key, msg]) => (
                                  <li key={key}>{msg}</li>
                                ))}
                              </ul>
                            </div>
                          </AlertDescription>
                        </Alert>
                      )}

                      {bulkSaveMutation.isError &&
                        !conflictAlertMessage &&
                        errorList.length === 0 && (
                          <p
                            role="alert"
                            className="mb-3 text-sm text-destructive"
                          >
                            {errorMessage(bulkSaveMutation.error)}
                          </p>
                        )}

                      {gradeSaveMessage && (
                        <p
                          role="status"
                          aria-live="polite"
                          className="mb-3 text-sm text-muted-foreground"
                        >
                          {gradeSaveMessage}
                        </p>
                      )}

                      {sortedRoster.length ? (
                        filteredRoster.length ? (
                          <>
                            <div className="overflow-x-auto">
                              <Table aria-label="Instructor gradebook matrix">
                                <TableHeader>
                                  <TableRow>
                                    <TableHead scope="col">Student</TableHead>
                                    <TableHead scope="col">
                                      Enrollment
                                    </TableHead>
                                    {visibleAssessments.map((asmt) => (
                                      <TableHead key={asmt.id} scope="col">
                                        <div className="flex flex-col gap-0.5">
                                          <span>{asmt.title}</span>
                                          <span className="text-xs font-normal text-muted-foreground">
                                            Max {asmt.points_possible} pts
                                          </span>
                                        </div>
                                      </TableHead>
                                    ))}
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {visibleRoster.map((student, rowIdx) => (
                                    <TableRow key={student.enrollment_id}>
                                      <TableCell className="min-w-44 align-top font-medium">
                                        {student.name}
                                      </TableCell>
                                      <TableCell className="align-top">
                                        <Badge
                                          variant={
                                            student.status === 'enrolled'
                                              ? 'outline'
                                              : 'secondary'
                                          }
                                        >
                                          {student.status}
                                        </Badge>
                                      </TableCell>
                                      {visibleAssessments.map(
                                        (asmt, colIdx) => {
                                          const cellKey = `${student.enrollment_id}:${asmt.id}`;
                                          const existing =
                                            gradesByCell.get(cellKey);
                                          const cellBatch = existing
                                            ? batches.find(
                                                (b) => b.id === existing.batch,
                                              )
                                            : selectedBatch;
                                          return (
                                            <GradeMatrixCell
                                              key={`${cellKey}-${existing?.version ?? 0}`}
                                              enrollmentId={
                                                student.enrollment_id
                                              }
                                              studentName={student.name}
                                              enrollmentStatus={student.status}
                                              assessment={asmt}
                                              rowIndex={rowIdx}
                                              colIndex={colIdx}
                                              rowCount={visibleRoster.length}
                                              colCount={
                                                visibleAssessments.length
                                              }
                                              batch={cellBatch}
                                              grade={existing}
                                              draftOverlay={drafts[cellKey]}
                                              cellError={
                                                cellErrors[cellKey] ?? null
                                              }
                                              onDraftChange={setCellDraft}
                                              onDiscardDraft={discardCellDraft}
                                              onSaveCell={(params) =>
                                                saveGrade.mutateAsync(params)
                                              }
                                              writesPending={writesPending}
                                            />
                                          );
                                        },
                                      )}
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>

                            <div
                              className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3 text-sm"
                              aria-label="Roster pagination"
                            >
                              <p className="text-muted-foreground">
                                Page {pagination.currentPage} of{' '}
                                {pagination.totalPages} (
                                {pagination.totalItems} matching student
                                {pagination.totalItems === 1 ? '' : 's'})
                              </p>
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setPage((p) => Math.max(1, p - 1))
                                  }
                                  disabled={pagination.currentPage <= 1}
                                >
                                  Previous page
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    setPage((p) =>
                                      Math.min(pagination.totalPages, p + 1),
                                    )
                                  }
                                  disabled={
                                    pagination.currentPage >=
                                    pagination.totalPages
                                  }
                                >
                                  Next page
                                </Button>
                              </div>
                            </div>
                          </>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            No students match the current search and grade
                            filters.
                          </p>
                        )
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No students are enrolled in this offering.
                        </p>
                      )}
                    </CardContent>
                  </Card>
                )}
            </>
          )}
        </>
      )}
      {!embedded && (
        <Button asChild variant="outline" className="self-start">
          <a href="/instructor">Back to instructor dashboard</a>
        </Button>
      )}
    </Container>
  );
}

export function StudentGradeSummary() {
  const session = useSession();
  const allowed = hasRole(session, 'student');
  const grades = useQuery({
    queryKey: ['academic', 'student-released-grades'],
    queryFn: ({ signal }) => getReleasedStudentGrades(signal),
    enabled: allowed,
  });
  const workspace = useQuery({
    queryKey: ['academic', 'student'],
    queryFn: ({ signal }) => getStudentWorkspace(signal),
    enabled: allowed,
  });
  if (!allowed) return null;
  if (grades.isPending || workspace.isPending)
    return <p role="status">Loading your released grades…</p>;
  if (grades.isError) return <p role="alert">{errorMessage(grades.error)}</p>;
  if (workspace.isError)
    return <p role="alert">{errorMessage(workspace.error)}</p>;

  const courses = new Map(
    workspace.data.courses.map((course) => [course.offering_id, course]),
  );
  return (
    <section aria-labelledby="released-grades-title">
      <h2 id="released-grades-title" className="mb-3 text-xl font-semibold">
        Released grades
      </h2>
      {grades.data.length ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Course</TableHead>
                <TableHead scope="col">Assessment</TableHead>
                <TableHead scope="col">Batch</TableHead>
                <TableHead scope="col">Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grades.data.map((grade) => {
                const course = courses.get(grade.offering);
                return (
                  <TableRow key={grade.id}>
                    <TableCell>
                      {course
                        ? `${course.course_code} · ${course.section}`
                        : 'Course'}
                    </TableCell>
                    <TableCell>{grade.assessment_title}</TableCell>
                    <TableCell>{grade.batch_name}</TableCell>
                    <TableCell>
                      {grade.state === 'scored'
                        ? `${grade.points_earned} / ${grade.points_possible}`
                        : stateLabel(grade.state)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No grades have been released for your courses yet.
        </p>
      )}
    </section>
  );
}
