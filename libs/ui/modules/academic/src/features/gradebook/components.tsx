'use client';

import { useState, type FormEvent, type ReactNode } from 'react';
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
  type GradeBatch,
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

function stateLabel(state: GradeState) {
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

type GradeDraft = {
  state: GradeState;
  points: string;
  reason: string;
};

function GradeEntryRow({
  enrollmentId,
  studentName,
  enrollmentStatus,
  assessmentId,
  pointsPossible,
  batch,
  grade,
  onSave,
}: {
  enrollmentId: string;
  studentName: string;
  enrollmentStatus: string;
  assessmentId: string;
  pointsPossible: string;
  batch: GradeBatch | undefined;
  grade: GradeRecord | undefined;
  onSave: (
    grade: GradeRecord | undefined,
    draft: GradeDraft,
    enrollmentId: string,
    assessmentId: string,
    batchId: string,
    studentName: string,
  ) => Promise<unknown>;
}) {
  const [state, setState] = useState<GradeState>(grade?.state ?? 'scored');
  const [points, setPoints] = useState(grade?.points_earned ?? '');
  const [reason, setReason] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const history = useQuery({
    queryKey: ['academic', 'grade-history', grade?.id],
    queryFn: ({ signal }) => getGradeHistory(grade!.id, signal),
    enabled: Boolean(grade && showHistory),
  });
  const save = useMutation({
    mutationFn: () =>
      onSave(
        grade,
        { state, points, reason },
        enrollmentId,
        assessmentId,
        grade?.batch ?? batch?.id ?? '',
        studentName,
      ),
  });
  const scoreLimit = grade?.points_possible ?? pointsPossible;
  const batchIsReleased = Boolean(batch?.released_at);
  const correctionIsReleased = grade?.batch === batch?.id && batchIsReleased;
  const reasonRequired = Boolean(
    grade ? correctionIsReleased : batchIsReleased,
  );
  const canSave =
    enrollmentStatus === 'enrolled' && (Boolean(grade) || Boolean(batch));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <TableRow>
      <TableCell className="min-w-44 font-medium">{studentName}</TableCell>
      <TableCell>
        <Badge
          variant={enrollmentStatus === 'enrolled' ? 'outline' : 'secondary'}
        >
          {enrollmentStatus}
        </Badge>
      </TableCell>
      <TableCell>
        {grade ? (
          <div className="min-w-64 space-y-2">
            <p className="text-sm">
              {stateLabel(grade.state)}
              {grade.state === 'scored' && (
                <span className="ml-2 font-medium">
                  {grade.points_earned} / {grade.points_possible}
                </span>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              {grade.batch_name} · version {grade.version}
            </p>
            {grade.state === 'scored' && Number(grade.points_earned) === 0 && (
              <Badge variant="secondary">Recorded zero</Badge>
            )}
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">Not entered</span>
        )}
      </TableCell>
      <TableCell>
        <form onSubmit={submit} className="min-w-64 space-y-3">
          <Field>
            <FieldLabel htmlFor={`state-${enrollmentId}`}>
              Grade state for {studentName}
            </FieldLabel>
            <NativeSelect
              id={`state-${enrollmentId}`}
              value={state}
              onChange={(event) => {
                save.reset();
                setState(event.target.value as GradeState);
              }}
              disabled={!canSave || save.isPending}
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
              <FieldLabel htmlFor={`points-${enrollmentId}`}>
                Points earned for {studentName} (out of {scoreLimit})
              </FieldLabel>
              <Input
                id={`points-${enrollmentId}`}
                type="number"
                inputMode="decimal"
                min="0"
                max={scoreLimit}
                step="0.01"
                required
                value={points}
                onChange={(event) => {
                  save.reset();
                  setPoints(event.target.value);
                }}
                disabled={!canSave || save.isPending}
                aria-describedby={`points-help-${enrollmentId}`}
              />
              <p
                id={`points-help-${enrollmentId}`}
                className="text-xs text-muted-foreground"
              >
                Enter 0 for a recorded zero. Use a grade state for work that was
                not scored.
              </p>
            </Field>
          )}
          {reasonRequired && (
            <Field>
              <FieldLabel htmlFor={`reason-${enrollmentId}`}>
                {grade
                  ? 'Correction reason'
                  : 'Reason for entering a released grade'}
              </FieldLabel>
              <Input
                id={`reason-${enrollmentId}`}
                value={reason}
                onChange={(event) => {
                  save.reset();
                  setReason(event.target.value);
                }}
                maxLength={255}
                required
                disabled={!canSave || save.isPending}
                aria-describedby={`reason-help-${enrollmentId}`}
              />
              <p
                id={`reason-help-${enrollmentId}`}
                className="text-xs text-muted-foreground"
              >
                A reason is recorded in the grade history because this batch has
                been released.
              </p>
            </Field>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              size="sm"
              disabled={!canSave || save.isPending}
            >
              {save.isPending
                ? 'Saving…'
                : grade
                  ? 'Save correction'
                  : 'Save grade'}
            </Button>
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
          {save.isError && (
            <p role="alert" className="text-sm text-destructive">
              {save.error instanceof ApiError && save.error.kind === 'conflict'
                ? 'This grade changed while you were editing it. The latest version is loading; review it before saving again.'
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
      </TableCell>
    </TableRow>
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
  const [assessmentChoice, setAssessmentChoice] = useState('');
  const [batchChoice, setBatchChoice] = useState('');
  const [batchName, setBatchName] = useState('');
  const [studentSearch, setStudentSearch] = useState('');
  const [gradeFilter, setGradeFilter] = useState<
    'all' | 'graded' | 'needs-grade'
  >('all');
  const [gradeSaveMessage, setGradeSaveMessage] = useState('');
  const [confirmRelease, setConfirmRelease] = useState(false);
  const active = board.data;
  const assessments = active?.assessments ?? [];
  const batches = active?.batches ?? [];
  const chosenAssessment =
    assessments.find((item) => item.id === assessmentChoice)?.id ??
    assessments[0]?.id ??
    '';
  const chosenBatch =
    batches.find((item) => item.id === batchChoice) ?? batches[0];
  const assessment = assessments.find((item) => item.id === chosenAssessment);
  const selectedBatch =
    batches.find((item) => item.id === batchChoice) ?? chosenBatch;
  const selectedOfferingData = offerings.find((item) => item.id === offeringId);
  const roster = selectedOfferingData?.roster ?? [];
  const assessmentGrades = new Map(
    (active?.grades ?? [])
      .filter((grade) => grade.assessment === chosenAssessment)
      .map((grade) => [grade.enrollment, grade]),
  );
  const gradedCount = roster.filter((student) =>
    assessmentGrades.has(student.enrollment_id),
  ).length;
  const needsGradeCount = roster.filter(
    (student) =>
      student.status === 'enrolled' &&
      !assessmentGrades.has(student.enrollment_id),
  ).length;
  const visibleRoster = roster.filter((student) => {
    const matchesSearch = student.name
      .toLocaleLowerCase()
      .includes(studentSearch.trim().toLocaleLowerCase());
    const isGraded = assessmentGrades.has(student.enrollment_id);
    return (
      matchesSearch &&
      (gradeFilter === 'all' ||
        (gradeFilter === 'graded'
          ? isGraded
          : student.status === 'enrolled' && !isGraded))
    );
  });
  const boardKey = ['academic', 'gradebook', offeringId] as const;

  const saveGrade = useMutation({
    mutationFn: async (input: {
      grade: GradeRecord | undefined;
      draft: GradeDraft;
      enrollmentId: string;
      assessmentId: string;
      batchId: string;
      studentName: string;
    }) => {
      const points = input.draft.state === 'scored' ? input.draft.points : null;
      if (input.grade) {
        const body: GradeCorrection = {
          expected_version: input.grade.version,
          state: input.draft.state,
          points_earned: points,
          reason: input.draft.reason,
        };
        return correctGrade(input.grade.id, body);
      }
      const body: GradeWrite = {
        enrollment: input.enrollmentId,
        assessment: input.assessmentId,
        batch: input.batchId,
        state: input.draft.state,
        points_earned: points,
        reason: input.draft.reason,
      };
      return createGrade(body);
    },
    onMutate: () => setGradeSaveMessage(''),
    onSuccess: async (_, input) => {
      const action = input.grade ? 'Grade correction saved' : 'Grade saved';
      setGradeSaveMessage(`${action} for ${input.studentName}.`);
      await queryClient.invalidateQueries({ queryKey: boardKey });
    },
    onError: (error, input) => {
      if (error instanceof ApiError && error.kind === 'conflict') {
        setGradeSaveMessage(
          `${input.studentName}'s grade changed while you were editing it. Review the latest version before saving again.`,
        );
        void queryClient.invalidateQueries({ queryKey: boardKey });
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
      await queryClient.invalidateQueries({ queryKey: boardKey });
    },
  });
  const writesPending =
    saveGrade.isPending || addBatch.isPending || release.isPending;

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
              <CardTitle>Offering and assessment</CardTitle>
              <CardDescription>
                Grades are saved against the selected approved assessment. Zero
                is a valid score; use a grade state for missing or exempt work.
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
                    setConfirmRelease(false);
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
                  Approved assessment
                </FieldLabel>
                <NativeSelect
                  id="gradebook-assessment"
                  value={chosenAssessment}
                  onChange={(event) => {
                    setGradeSaveMessage('');
                    setAssessmentChoice(event.target.value);
                  }}
                  disabled={
                    !assessments.length || board.isPending || writesPending
                  }
                >
                  {assessments.length ? (
                    assessments.map((item) => (
                      <NativeSelectOption key={item.id} value={item.id}>
                        {item.title} · {item.points_possible} points
                      </NativeSelectOption>
                    ))
                  ) : (
                    <NativeSelectOption value="">
                      No approved assessments
                    </NativeSelectOption>
                  )}
                </NativeSelect>
              </Field>
              {assessment && (
                <p className="text-sm text-muted-foreground md:col-span-2">
                  {selectedOfferingData?.course} · maximum score{' '}
                  {assessment.points_possible}
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
                              {batch.released_at ? ' · Released' : ''}
                            </NativeSelectOption>
                          ))
                        ) : (
                          <NativeSelectOption value="">
                            Create a batch to begin
                          </NativeSelectOption>
                        )}
                      </NativeSelect>
                    </Field>
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

              {selectedBatch && chosenAssessment && selectedOfferingData && (
                <Card>
                  <CardHeader>
                    <CardTitle>{assessment?.title} roster</CardTitle>
                    <CardDescription>
                      {selectedOfferingData.label} · {selectedBatch.name} ·{' '}
                      {selectedOfferingData.roster.length} students
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="mb-5 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-md border p-3">
                        <p className="text-sm text-muted-foreground">Roster</p>
                        <p className="text-2xl font-semibold">
                          {roster.length}
                        </p>
                      </div>
                      <div className="rounded-md border p-3">
                        <p className="text-sm text-muted-foreground">
                          Grades entered
                        </p>
                        <p className="text-2xl font-semibold">{gradedCount}</p>
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
                    <div className="mb-4 grid gap-4 sm:grid-cols-2">
                      <Field>
                        <FieldLabel htmlFor="gradebook-student-search">
                          Find a student
                        </FieldLabel>
                        <Input
                          id="gradebook-student-search"
                          type="search"
                          value={studentSearch}
                          onChange={(event) =>
                            setStudentSearch(event.target.value)
                          }
                        />
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="gradebook-grade-filter">
                          Show students
                        </FieldLabel>
                        <NativeSelect
                          id="gradebook-grade-filter"
                          value={gradeFilter}
                          onChange={(event) =>
                            setGradeFilter(
                              event.target.value as typeof gradeFilter,
                            )
                          }
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
                    </div>
                    {gradeSaveMessage && (
                      <p
                        role="status"
                        className="mb-3 text-sm text-muted-foreground"
                      >
                        {gradeSaveMessage}
                      </p>
                    )}
                    {roster.length ? (
                      visibleRoster.length ? (
                        <div className="overflow-x-auto">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead scope="col">Student</TableHead>
                                <TableHead scope="col">Enrollment</TableHead>
                                <TableHead scope="col">Current grade</TableHead>
                                <TableHead scope="col">
                                  Enter or correct grade
                                </TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {visibleRoster.map((student) => {
                                const existing = assessmentGrades.get(
                                  student.enrollment_id,
                                );
                                return (
                                  <GradeEntryRow
                                    key={`${student.enrollment_id}-${chosenAssessment}-${existing?.version ?? 0}`}
                                    enrollmentId={student.enrollment_id}
                                    studentName={student.name}
                                    enrollmentStatus={student.status}
                                    assessmentId={chosenAssessment}
                                    pointsPossible={
                                      assessment?.points_possible ?? '0'
                                    }
                                    batch={
                                      existing
                                        ? batches.find(
                                            (item) =>
                                              item.id === existing.batch,
                                          )
                                        : selectedBatch
                                    }
                                    grade={existing}
                                    onSave={(
                                      grade,
                                      draft,
                                      enrollmentId,
                                      assessmentId,
                                      batchId,
                                      studentName,
                                    ) =>
                                      saveGrade.mutateAsync({
                                        grade,
                                        draft,
                                        enrollmentId,
                                        assessmentId,
                                        batchId,
                                        studentName,
                                      })
                                    }
                                  />
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
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
