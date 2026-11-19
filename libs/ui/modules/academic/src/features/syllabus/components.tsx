'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { errorMessage } from '@outcometrik/access';
import {
  Badge,
  Button,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import {
  changeProgramOutcomeSet,
  getProgramOutcomeSets,
  getProgramOutcomes,
  type ProgramOutcomeSet,
  changeSyllabus,
  deleteSyllabusPOContribution,
  getSyllabi,
<<<<<<< HEAD
  saveSyllabusPOContribution,
=======
  getSyllabusMappingValidation,
  replaceAssessmentLOMappings,
  replaceLOPOMappings,
>>>>>>> origin/main
  type Assessment,
  type CoursePOContribution,
  type Outcome,
  type Syllabus,
} from './api';

function OutcomeForm({
  value,
  save,
  pending,
}: {
  value?: Outcome;
  save: (data: object) => void;
  pending: boolean;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save({
      code: data.get('code'),
      description: data.get('description'),
      order: Number(data.get('order')),
    });
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">
        {value ? `Edit ${value.code}` : 'Add learning outcome'}
      </h5>
      <FieldGroup>
        <Field>
          <FieldLabel>
            Code
            <Input
              name="code"
              required
              maxLength={32}
              defaultValue={value?.code}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Description
            <Input
              name="description"
              required
              defaultValue={value?.description}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Order
            <Input
              name="order"
              type="number"
              min="0"
              required
              defaultValue={value?.order}
            />
          </FieldLabel>
        </Field>
      </FieldGroup>
      <Button type="submit" disabled={pending}>
        {value ? 'Save outcome' : 'Add outcome'}
      </Button>
    </form>
  );
}
function AssessmentForm({
  value,
  save,
  pending,
}: {
  value?: Assessment;
  save: (data: object) => void;
  pending: boolean;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save({
      code: data.get('code'),
      kind: data.get('kind'),
      order: Number(data.get('order')),
      max_points: data.get('max_points'),
      is_required: data.has('is_required'),
      is_active: data.has('is_active'),
    });
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">
        {value ? `Edit ${value.code}` : 'Add assessment'}
      </h5>
      <FieldGroup>
        <Field>
          <FieldLabel>
            Code
            <Input
              name="code"
              required
              maxLength={32}
              defaultValue={value?.code}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Kind
            <NativeSelect name="kind" defaultValue={value?.kind ?? 'exam'}>
              {['exam', 'homework', 'project', 'quiz', 'lab', 'other'].map(
                (kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ),
              )}
            </NativeSelect>
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Order
            <Input
              name="order"
              type="number"
              min="0"
              required
              defaultValue={value?.order}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Maximum points
            <Input
              name="max_points"
              type="number"
              min="0.01"
              step="0.01"
              required
              defaultValue={value?.max_points}
            />
          </FieldLabel>
        </Field>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            name="is_required"
            defaultChecked={value?.is_required ?? true}
          />{' '}
          Required
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            name="is_active"
            defaultChecked={value?.is_active ?? true}
          />{' '}
          Active
        </label>
      </FieldGroup>
      <Button type="submit" disabled={pending}>
        {value ? 'Save assessment' : 'Add assessment'}
      </Button>
    </form>
  );
}

<<<<<<< HEAD
function CoursePOContributionSection({
  syllabus,
  programId,
  canApprove,
  onChanged,
}: {
  syllabus: Syllabus;
  programId?: string;
  canApprove: boolean;
  onChanged: () => void;
}) {
  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', programId],
    queryFn: ({ signal }) => getProgramOutcomeSets(programId ?? '', signal),
    enabled: Boolean(programId),
  });
  const boundSet = poSetsQuery.data?.find(
    (item) => item.version === syllabus.po_set_version,
  );
  const outcomesQuery = useQuery({
    queryKey: ['academic', 'po-set-outcomes', boundSet?.id],
    queryFn: ({ signal }) => getProgramOutcomes(boundSet?.id ?? '', signal),
    enabled: Boolean(boundSet?.id),
  });

  const saveMutation = useMutation({
    mutationFn: ({
      program_outcome,
      weight,
      contributionId,
    }: {
      program_outcome: string;
      weight: number;
      contributionId?: string;
    }) =>
      saveSyllabusPOContribution(
        syllabus.id,
        { program_outcome, weight },
        contributionId,
      ),
    onSuccess: () => onChanged(),
  });

  const deleteMutation = useMutation({
    mutationFn: (contributionId: string) =>
      deleteSyllabusPOContribution(syllabus.id, contributionId),
    onSuccess: () => onChanged(),
  });

  const contributions: CoursePOContribution[] = syllabus.po_contributions ?? [];
  const isEditable = canApprove && syllabus.status === 'draft';
  const pending = saveMutation.isPending || deleteMutation.isPending;

  return (
    <section
      className="space-y-3"
      aria-label="Course-to-PO Contribution Weights (1–5)"
    >
      <div className="space-y-1">
        <h4 className="font-medium">Course-to-PO Contribution Weights (1–5)</h4>
        <p className="text-xs text-muted-foreground">
          Governance policy: Program Coordinator at offering syllabus version
          level. Unmapped POs produce <code>NOT_ASSESSED</code> (never 0).
        </p>
      </div>
      {syllabus.status === 'approved' && (
        <p className="text-xs text-muted-foreground">
          This syllabus version is approved and its contribution weights are
          locked. Create a new syllabus revision to change weights (which marks
          prior calculations stale without mutating earlier publications).
        </p>
      )}
      {saveMutation.isError && (
        <p role="alert">{errorMessage(saveMutation.error)}</p>
      )}
      {deleteMutation.isError && (
        <p role="alert">{errorMessage(deleteMutation.error)}</p>
      )}
      {outcomesQuery.isPending && boundSet && (
        <p role="status">Loading bound program outcomes…</p>
      )}
      {outcomesQuery.isError && (
        <p role="alert">{errorMessage(outcomesQuery.error)}</p>
      )}
      {outcomesQuery.data ? (
        <ul className="space-y-2">
          {outcomesQuery.data.map((po) => {
            const existing = contributions.find(
              (c) =>
                c.program_outcome === po.id ||
                c.program_outcome_code === po.code,
            );
            return (
              <li
                key={po.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm"
              >
                <div>
                  <span className="font-medium">{po.code}</span>: {po.label}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {existing ? (
                    <Badge variant="outline">Weight {existing.weight}/5</Badge>
                  ) : (
                    <Badge variant="secondary">Not mapped (NOT_ASSESSED)</Badge>
                  )}
                  {isEditable && (
                    <form
                      className="flex items-center gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const data = new FormData(event.currentTarget);
                        const rawWeight = Number(data.get('weight'));
                        saveMutation.mutate({
                          program_outcome: po.id,
                          weight: rawWeight,
                          contributionId: existing?.id,
                        });
                      }}
                    >
                      <label className="sr-only" htmlFor={`po-weight-${po.id}`}>
                        {po.code} contribution weight
                      </label>
                      <NativeSelect
                        id={`po-weight-${po.id}`}
                        name="weight"
                        defaultValue={String(existing?.weight ?? 3)}
                        aria-label={`${po.code} contribution weight`}
                      >
                        {[1, 2, 3, 4, 5].map((w) => (
                          <option key={w} value={w}>
                            {w}
                          </option>
                        ))}
                      </NativeSelect>
                      <Button type="submit" size="sm" disabled={pending}>
                        {existing ? 'Update weight' : 'Assign weight'}
                      </Button>
                      {existing && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={pending}
                          onClick={() => deleteMutation.mutate(existing.id)}
                        >
                          Remove
                        </Button>
                      )}
                    </form>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : contributions.length ? (
        <ul className="space-y-1 text-sm">
          {contributions.map((item) => (
            <li key={item.id} className="flex items-center gap-2">
              <span className="font-medium">{item.program_outcome_code}</span>
              <Badge variant="outline">Weight {item.weight}/5</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          No course-to-PO contribution weights mapped (NOT_ASSESSED).
        </p>
      )}
=======
function SyllabusMappingStudio({
  version,
  canDraft,
  onSaved,
}: {
  version: Syllabus;
  canDraft: boolean;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const valKey = [
    'academic',
    'syllabus-mapping-validation',
    version.id,
    version.mapping_revision ?? 1,
  ];
  const validationQuery = useQuery({
    queryKey: valKey,
    queryFn: ({ signal }) => getSyllabusMappingValidation(version.id, signal),
  });

  const aLoLookup = new Map<string, string>();
  for (const m of version.assessment_lo_mappings ?? []) {
    if (m.is_active && Number(m.weight) > 0) {
      aLoLookup.set(`${m.assessment}:${m.learning_outcome}`, m.weight);
    }
  }

  const loPoLookup = new Map<string, number>();
  for (const m of version.lo_po_mappings ?? []) {
    if (m.is_active && m.weight >= 1) {
      loPoLookup.set(`${m.learning_outcome}:${m.program_outcome}`, m.weight);
    }
  }

  const aLoMutation = useMutation({
    mutationFn: (
      mappings: Array<{
        assessment: string;
        learning_outcome: string;
        weight: string;
      }>,
    ) =>
      replaceAssessmentLOMappings(
        version.id,
        version.mapping_revision ?? 1,
        mappings,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: valKey });
      onSaved();
    },
  });

  const loPoMutation = useMutation({
    mutationFn: (
      mappings: Array<{
        learning_outcome: string;
        program_outcome: string;
        weight: number;
      }>,
    ) =>
      replaceLOPOMappings(version.id, version.mapping_revision ?? 1, mappings),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: valKey });
      onSaved();
    },
  });

  const editable = canDraft && version.status === 'draft';
  const report = validationQuery.data;
  const loStatusMap = new Map(
    (report?.lo_statuses ?? []).map((item) => [item.learning_outcome_id, item]),
  );

  function submitALo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const mappings: Array<{
      assessment: string;
      learning_outcome: string;
      weight: string;
    }> = [];
    for (const assessment of version.assessments) {
      for (const lo of version.learning_outcomes) {
        const raw = String(
          form.get(`alo_${assessment.id}_${lo.id}`) ?? '',
        ).trim();
        if (raw !== '' && Number(raw) > 0) {
          mappings.push({
            assessment: assessment.id,
            learning_outcome: lo.id,
            weight: raw,
          });
        }
      }
    }
    aLoMutation.mutate(mappings);
  }

  function submitLoPo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const mappings: Array<{
      learning_outcome: string;
      program_outcome: string;
      weight: number;
    }> = [];
    for (const lo of version.learning_outcomes) {
      for (const po of report?.po_statuses ?? []) {
        const raw = Number(
          form.get(`lopo_${lo.id}_${po.program_outcome_id}`) ?? 0,
        );
        if (raw >= 1 && raw <= 5) {
          mappings.push({
            learning_outcome: lo.id,
            program_outcome: po.program_outcome_id,
            weight: raw,
          });
        }
      }
    }
    loPoMutation.mutate(mappings);
  }

  return (
    <section
      className="space-y-4 rounded border p-3"
      aria-label="Curriculum Mapping Matrices"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-medium">
          Curriculum mapping matrices (A→LO & LO→PO)
        </h4>
        <Badge variant="outline">
          Revision v{version.mapping_revision ?? 1}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Assessment→LO weights are nonnegative relative values (no sum-to-100
        constraint). Active LO→PO links carry integer weights 1–5; unmapped LOs
        are UNMAPPED and unassessed POs are NOT_ASSESSED (never numeric zero).
      </p>

      {validationQuery.isPending && (
        <p role="status">Validating mapping matrices…</p>
      )}
      {validationQuery.isError && (
        <p role="alert">{errorMessage(validationQuery.error)}</p>
      )}
      {aLoMutation.isError && (
        <p role="alert">{errorMessage(aLoMutation.error)}</p>
      )}
      {loPoMutation.isError && (
        <p role="alert">{errorMessage(loPoMutation.error)}</p>
      )}

      {version.assessments.length > 0 &&
      version.learning_outcomes.length > 0 ? (
        <form
          key={`alo-${version.id}-${version.mapping_revision ?? 1}`}
          onSubmit={submitALo}
          className="space-y-3"
        >
          <h5 className="text-sm font-medium">
            1. Assessment → Learning Outcome (A→LO) relative weights
          </h5>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Assessment</TableHead>
                {version.learning_outcomes.map((lo) => {
                  const statusItem = loStatusMap.get(lo.id);
                  return (
                    <TableHead key={lo.id}>
                      <div className="flex flex-col gap-1">
                        <span>{lo.code}</span>
                        {statusItem && (
                          <Badge
                            variant={
                              statusItem.status === 'MAPPED'
                                ? 'outline'
                                : 'secondary'
                            }
                          >
                            {statusItem.status === 'MAPPED'
                              ? `MAPPED (${statusItem.total_assessment_weight})`
                              : 'UNMAPPED'}
                          </Badge>
                        )}
                      </div>
                    </TableHead>
                  );
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {version.assessments.map((assessment) => (
                <TableRow key={assessment.id}>
                  <TableCell className="font-medium">
                    {assessment.code}{' '}
                    <span className="text-xs text-muted-foreground">
                      ({assessment.max_points} pts)
                    </span>
                  </TableCell>
                  {version.learning_outcomes.map((lo) => {
                    const currentWeight =
                      aLoLookup.get(`${assessment.id}:${lo.id}`) ?? '0';
                    return (
                      <TableCell key={lo.id}>
                        {editable ? (
                          <Input
                            aria-label={`${assessment.code} to ${lo.code} weight`}
                            name={`alo_${assessment.id}_${lo.id}`}
                            type="number"
                            min="0"
                            step="0.01"
                            defaultValue={currentWeight}
                            className="w-24"
                          />
                        ) : (
                          <span>
                            {Number(currentWeight) > 0 ? currentWeight : '—'}
                          </span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {editable && (
            <Button type="submit" disabled={aLoMutation.isPending}>
              Save A→LO matrix
            </Button>
          )}
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">
          Add at least one learning outcome and one assessment to configure the
          A→LO matrix.
        </p>
      )}

      {version.learning_outcomes.length > 0 &&
      (report?.po_statuses.length ?? 0) > 0 ? (
        <form
          key={`lopo-${version.id}-${version.mapping_revision ?? 1}`}
          onSubmit={submitLoPo}
          className="space-y-3 border-t pt-3"
        >
          <h5 className="text-sm font-medium">
            2. Learning Outcome → Program Outcome (LO→PO) integer weights (1–5)
          </h5>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>LO</TableHead>
                {report?.po_statuses.map((po) => (
                  <TableHead key={po.program_outcome_id}>
                    <div className="flex flex-col gap-1">
                      <span>{po.code}</span>
                      <Badge
                        variant={
                          po.status === 'ASSESSED' ? 'outline' : 'secondary'
                        }
                      >
                        {po.status === 'ASSESSED'
                          ? `ASSESSED (Σ=${po.total_lo_weight})`
                          : 'NOT_ASSESSED'}
                      </Badge>
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {version.learning_outcomes.map((lo) => (
                <TableRow key={lo.id}>
                  <TableCell className="font-medium">{lo.code}</TableCell>
                  {report?.po_statuses.map((po) => {
                    const currentWeight =
                      loPoLookup.get(`${lo.id}:${po.program_outcome_id}`) ?? 0;
                    return (
                      <TableCell key={po.program_outcome_id}>
                        {editable ? (
                          <NativeSelect
                            aria-label={`${lo.code} to ${po.code} weight`}
                            name={`lopo_${lo.id}_${po.program_outcome_id}`}
                            defaultValue={String(currentWeight)}
                          >
                            <option value="0">— (0)</option>
                            {[1, 2, 3, 4, 5].map((w) => (
                              <option key={w} value={String(w)}>
                                {w}
                              </option>
                            ))}
                          </NativeSelect>
                        ) : (
                          <span>{currentWeight > 0 ? currentWeight : '—'}</span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {editable && (
            <Button type="submit" disabled={loPoMutation.isPending}>
              Save LO→PO matrix
            </Button>
          )}
        </form>
      ) : null}

      {report && (
        <div
          className="space-y-2 border-t pt-3 text-sm"
          aria-label="Mapping diagnostics"
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">Pre-approval readiness:</span>
            <Badge
              variant={report.is_valid_for_approval ? 'outline' : 'secondary'}
            >
              {report.is_valid_for_approval
                ? 'Ready for approval'
                : 'Issues detected'}
            </Badge>
          </div>
          {report.errors.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm" role="alert">
              {report.errors.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          )}
        </div>
      )}
>>>>>>> origin/main
    </section>
  );
}

export function SyllabusWorkspace({
  offering,
  programId,
  canDraft,
  canApprove,
}: {
  offering: string;
  programId?: string;
  canDraft: boolean;
  canApprove: boolean;
}) {
  const queryClient = useQueryClient();
  const key = ['academic', 'syllabi', offering];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getSyllabi(offering, signal),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body?: object;
      method?: string;
    }) => changeSyllabus(path, body, method),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const versions = query.data ?? [];
  const version: Syllabus | undefined =
    versions.find((item) => item.id === selected) ??
    versions.find((item) => item.status === 'draft') ??
    versions.find((item) => item.status === 'approved') ??
    versions.at(-1);
  const run = (path: string, body?: object, method?: string) =>
    mutation.mutate({ path, body, method });
  return (
    <section className="mt-5 space-y-4 border-t pt-4" aria-label="Syllabus">
      <h3 className="font-semibold">Syllabus</h3>
      {query.isPending && <p role="status">Loading syllabus versions…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {mutation.isPending && <p role="status">Saving changes…</p>}
      {query.isSuccess && !versions.length && <p>No syllabus versions yet.</p>}
      {query.isSuccess &&
        canDraft &&
        !versions.some(
          (item) => item.status === 'draft' || item.status === 'approved',
        ) && (
          <Button
            disabled={mutation.isPending}
            onClick={() => run('', { offering })}
          >
            Create draft
          </Button>
        )}
      {version && (
        <>
          <label className="block">
            Version{' '}
            <NativeSelect
              value={version.id}
              onChange={(event) => setSelected(event.target.value)}
            >
              {versions.map((item) => (
                <option key={item.id} value={item.id}>
                  Version {item.version} · {item.status}
                </option>
              ))}
            </NativeSelect>
          </label>
          <p className="text-sm">
            {version.status === 'approved'
              ? `Approved ${version.approved_at ? new Date(version.approved_at).toLocaleString() : ''}`
              : version.status === 'draft'
                ? 'Draft — changes are editable until approval.'
                : 'Retired — preserved for history.'}{' '}
            {version.po_set_version !== null &&
              `PO set version ${version.po_set_version}.`}
          </p>
          {canDraft && version.status === 'draft' && (
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => run(`${version.id}/bind-active-po-set/`)}
            >
              Bind active outcome set
            </Button>
          )}
          {canApprove && version.status === 'draft' && (
            <Button
              disabled={mutation.isPending}
              onClick={() => run(`${version.id}/approve/`)}
            >
              Approve syllabus
            </Button>
          )}
          {canDraft &&
            version.status === 'approved' &&
            !versions.some((item) => item.status === 'draft') && (
              <Button
                disabled={mutation.isPending}
                onClick={() => {
                  setSelected(null);
                  run(`${version.id}/revise/`);
                }}
              >
                Create revision
              </Button>
            )}
          {canDraft &&
            version.status === 'draft' &&
            version.learning_outcomes.length === 0 &&
            version.assessments.length === 0 &&
            (version.po_contributions?.length ?? 0) === 0 && (
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() => run(`${version.id}/retire/`)}
              >
                Retire empty draft
              </Button>
            )}
          <section className="space-y-3">
            <h4 className="font-medium">Learning outcomes</h4>
            {!version.learning_outcomes.length && (
              <p>No learning outcomes yet.</p>
            )}
            {version.learning_outcomes.map((item) =>
              canDraft && version.status === 'draft' ? (
                <OutcomeForm
                  key={item.id}
                  value={item}
                  pending={mutation.isPending}
                  save={(data) =>
                    run(
                      `${version.id}/learning-outcomes/${item.id}/`,
                      data,
                      'PATCH',
                    )
                  }
                />
              ) : (
                <p key={item.id}>
                  {item.order}. {item.code}: {item.description}
                </p>
              ),
            )}
            {canDraft && version.status === 'draft' && (
              <OutcomeForm
                key={`${version.id}-new-outcome`}
                pending={mutation.isPending}
                save={(data) => run(`${version.id}/learning-outcomes/`, data)}
              />
            )}
          </section>
          <section className="space-y-3">
            <h4 className="font-medium">Assessments</h4>
            {!version.assessments.length && <p>No assessments yet.</p>}
            {version.assessments.map((item) =>
              canDraft && version.status === 'draft' ? (
                <AssessmentForm
                  key={item.id}
                  value={item}
                  pending={mutation.isPending}
                  save={(data) =>
                    run(`${version.id}/assessments/${item.id}/`, data, 'PATCH')
                  }
                />
              ) : (
                <p key={item.id}>
                  {item.order}. {item.code} · {item.kind} · {item.max_points}{' '}
                  points · {item.is_required ? 'required' : 'optional'} ·{' '}
                  {item.is_active ? 'active' : 'inactive'}
                </p>
              ),
            )}
            {canDraft && version.status === 'draft' && (
              <AssessmentForm
                key={`${version.id}-new-assessment`}
                pending={mutation.isPending}
                save={(data) => run(`${version.id}/assessments/`, data)}
              />
            )}
          </section>
<<<<<<< HEAD
          <CoursePOContributionSection
            syllabus={version}
            programId={programId}
            canApprove={canApprove}
            onChanged={() =>
=======
          <SyllabusMappingStudio
            version={version}
            canDraft={canDraft}
            onSaved={() =>
>>>>>>> origin/main
              void queryClient.invalidateQueries({ queryKey: key })
            }
          />
        </>
      )}
    </section>
  );
}

export function ProgramOutcomeSets({ program }: { program: string }) {
  const client = useQueryClient();
  const key = ['academic', 'po-sets', program];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getProgramOutcomeSets(program, signal),
  });
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) =>
      changeProgramOutcomeSet(path, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      path: '',
      body: {
        program,
        version: Number(data.get('version')),
        effective_date: data.get('effective_date'),
        source_reference: data.get('source_reference'),
      },
    });
  }
  return (
    <section className="space-y-3">
      <h3 className="font-medium">Program outcome sets</h3>
      {query.isPending && <p role="status">Loading outcome sets…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {query.data?.length === 0 && (
        <p>
          No outcome sets yet. An active set is required to create a syllabus.
        </p>
      )}
      {query.data?.map((set) => (
        <OutcomeSetEditor
          key={set.id}
          set={set}
          onActivated={() => client.invalidateQueries({ queryKey: key })}
        />
      ))}
      <form onSubmit={create} className="space-y-3 rounded border p-3">
        <h4 className="font-medium">Register outcome set</h4>
        <FieldGroup>
          <Field>
            <FieldLabel>
              Version
              <Input name="version" type="number" min="1" required />
            </FieldLabel>
          </Field>
          <Field>
            <FieldLabel>
              Effective date
              <Input name="effective_date" type="date" required />
            </FieldLabel>
          </Field>
          <Field>
            <FieldLabel>
              Source reference
              <Input name="source_reference" required />
            </FieldLabel>
          </Field>
        </FieldGroup>
        <Button type="submit" disabled={mutation.isPending}>
          Register outcome set
        </Button>
      </form>
    </section>
  );
}

function OutcomeSetEditor({
  set,
  onActivated,
}: {
  set: ProgramOutcomeSet;
  onActivated: () => void;
}) {
  const client = useQueryClient();
  const key = ['academic', 'po-set-outcomes', set.id];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getProgramOutcomes(set.id, signal),
  });
  const mutation = useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body?: object;
      method?: string;
    }) => changeProgramOutcomeSet(path, body, method),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: key });
      onActivated();
    },
  });
  const missing = Array.from({ length: 11 }, (_, i) => i + 1).filter(
    (number) => !query.data?.some((outcome) => outcome.code === `PO${number}`),
  );
  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const order = Number(data.get('order'));
    mutation.mutate(
      {
        path: `${set.id}/outcomes/`,
        body: {
          code: `PO${order}`,
          order,
          label: data.get('label'),
          description: data.get('description'),
          source_reference: data.get('source_reference'),
        },
      },
      { onSuccess: () => form.reset() },
    );
  }
  return (
    <section
      className="space-y-3 rounded border p-3"
      aria-label={`Outcome set version ${set.version}`}
    >
      <h4 className="font-medium">
        Version {set.version} ·{' '}
        {set.active ? 'active' : set.activated_at ? 'retired' : 'draft'}
      </h4>
      <p>
        {set.effective_date} · {set.source_reference}
      </p>
      {query.isPending && <p role="status">Loading outcome definitions…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {query.data && (
        <>
          <p>{query.data.length} of 11 outcome definitions</p>
          <ul>
            {query.data.map((outcome) => (
              <li key={outcome.id}>
                {set.activated_at ? (
                  <p>
                    {outcome.code}: {outcome.label} — {outcome.description} (
                    {outcome.source_reference})
                  </p>
                ) : (
                  <form
                    className="space-y-2 border-b py-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const data = new FormData(event.currentTarget);
                      mutation.mutate({
                        path: `${set.id}/outcomes/${outcome.id}/`,
                        method: 'PATCH',
                        body: {
                          label: data.get('label'),
                          description: data.get('description'),
                          source_reference: data.get('source_reference'),
                        },
                      });
                    }}
                  >
                    <h5 className="font-medium">Edit {outcome.code}</h5>
                    <FieldGroup>
                      <Field>
                        <FieldLabel>
                          Label
                          <Input
                            name="label"
                            defaultValue={outcome.label}
                            required
                          />
                        </FieldLabel>
                      </Field>
                      <Field>
                        <FieldLabel>
                          Description
                          <Input
                            name="description"
                            defaultValue={outcome.description}
                            required
                          />
                        </FieldLabel>
                      </Field>
                      <Field>
                        <FieldLabel>
                          Source reference
                          <Input
                            name="source_reference"
                            defaultValue={outcome.source_reference}
                            required
                          />
                        </FieldLabel>
                      </Field>
                    </FieldGroup>
                    <Button type="submit" disabled={mutation.isPending}>
                      Save {outcome.code}
                    </Button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {query.data && !set.activated_at && missing.length > 0 && (
        <form onSubmit={add} className="space-y-3">
          <h5 className="font-medium">Add outcome definition</h5>
          <FieldGroup>
            <Field>
              <FieldLabel>
                Outcome
                <NativeSelect name="order">
                  {missing.map((number) => (
                    <option key={number} value={number}>
                      PO{number}
                    </option>
                  ))}
                </NativeSelect>
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Label
                <Input name="label" required />
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Description
                <Input name="description" required />
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Source reference
                <Input name="source_reference" required />
              </FieldLabel>
            </Field>
          </FieldGroup>
          <Button type="submit" disabled={mutation.isPending}>
            Add definition
          </Button>
        </form>
      )}
      {query.data && !set.activated_at && missing.length === 0 && (
        <Button
          variant="outline"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ path: `${set.id}/activate/` })}
        >
          Activate version {set.version}
        </Button>
      )}
    </section>
  );
}
