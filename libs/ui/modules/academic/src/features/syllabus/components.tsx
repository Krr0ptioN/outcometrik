'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { errorMessage } from '@outcometrik/access';
import {
  Button,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
} from '@outcometrik/ui';
import {
  changeProgramOutcomeSet,
  getProgramOutcomeSets,
  getProgramOutcomes,
  type ProgramOutcomeSet,
  changeSyllabus,
  getSyllabi,
  type Assessment,
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
export function SyllabusWorkspace({
  offering,
  canDraft,
  canApprove,
}: {
  offering: string;
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
            version.assessments.length === 0 && (
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
