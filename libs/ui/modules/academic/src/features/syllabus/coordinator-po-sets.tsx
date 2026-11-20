'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useId, useMemo, useState, type FormEvent } from 'react';
import { CheckCircle2, Lock, Pencil, Plus, ShieldCheck } from 'lucide-react';
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
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  NativeSelectOption,
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
import { getCoordinatorWorkspace } from '../workspace/api';
import {
  changeProgramOutcomeSet,
  getProgramOutcomeSets,
  getProgramOutcomes,
  type ProgramOutcome,
  type ProgramOutcomeSet,
} from './api';

export type PoSetLifecycleState = 'active' | 'archived' | 'draft';

export function resolvePoSetLifecycle(
  poSet: Pick<ProgramOutcomeSet, 'active' | 'activated_at'>,
): PoSetLifecycleState {
  if (poSet.active) return 'active';
  if (poSet.activated_at !== null) return 'archived';
  return 'draft';
}

function PoSetStatusBadge({ poSet }: { poSet: ProgramOutcomeSet }) {
  const state = resolvePoSetLifecycle(poSet);
  if (state === 'active') {
    return <StatusDot variant="success" label={`v${poSet.version} Active`} />;
  }
  if (state === 'archived') {
    return <StatusDot variant="neutral" label={`v${poSet.version} Archived`} />;
  }
  return <StatusDot variant="warning" label={`v${poSet.version} Draft`} />;
}

export function CoordinatorPOSetManager() {
  const queryClient = useQueryClient();
  const programSelectId = useId();

  const workspaceQuery = useQuery({
    queryKey: ['academic', 'coordinator'],
    queryFn: ({ signal }) => getCoordinatorWorkspace(signal),
  });

  const programs = useMemo(
    () => workspaceQuery.data?.programs ?? [],
    [workspaceQuery.data],
  );
  const [selectedProgramId, setSelectedProgramId] = useState<string>('');
  const activeProgramId =
    selectedProgramId && programs.some((p) => p.id === selectedProgramId)
      ? selectedProgramId
      : (programs[0]?.id ?? '');

  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', activeProgramId],
    queryFn: ({ signal }) => getProgramOutcomeSets(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const poSets = useMemo(
    () => [...(poSetsQuery.data ?? [])].sort((a, b) => b.version - a.version),
    [poSetsQuery.data],
  );

  const [selectedSetId, setSelectedSetId] = useState<string>('');
  const activeSet =
    poSets.find((s) => s.id === selectedSetId) ??
    poSets.find((s) => s.active) ??
    poSets[0] ??
    null;

  const outcomesQuery = useQuery({
    queryKey: ['academic', 'po-set-outcomes', activeSet?.id ?? null],
    queryFn: ({ signal }) => getProgramOutcomes(activeSet?.id ?? '', signal),
    enabled: Boolean(activeSet?.id),
  });

  const outcomes = useMemo(
    () => [...(outcomesQuery.data ?? [])].sort((a, b) => a.order - b.order),
    [outcomesQuery.data],
  );

  const [createDraftOpen, setCreateDraftOpen] = useState(false);
  const [activateDialogOpen, setActivateDialogOpen] = useState(false);
  const [activateEffectiveDate, setActivateEffectiveDate] = useState<string>(
    new Date().toISOString().slice(0, 10),
  );
  const [editingOutcome, setEditingOutcome] = useState<ProgramOutcome | null>(
    null,
  );
  const [addingOutcomeOpen, setAddingOutcomeOpen] = useState(false);

  const createDraftMutation = useMutation({
    mutationFn: (payload: {
      program: string;
      effective_date: string;
      source_reference: string;
    }) => changeProgramOutcomeSet('', payload, 'POST'),
    onSuccess: async () => {
      setCreateDraftOpen(false);
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-sets', activeProgramId],
      });
    },
  });

  const activateMutation = useMutation({
    mutationFn: (args: { id: string; effective_date?: string }) =>
      changeProgramOutcomeSet(
        `${args.id}/activate/`,
        args.effective_date ? { effective_date: args.effective_date } : {},
        'POST',
      ),
    onSuccess: async () => {
      setActivateDialogOpen(false);
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-sets', activeProgramId],
      });
    },
  });

  const saveOutcomeMutation = useMutation({
    mutationFn: (args: {
      poSetId: string;
      outcomeId?: string;
      body: {
        code: string;
        label: string;
        description: string;
        source_reference: string;
        order: number;
      };
    }) =>
      args.outcomeId
        ? changeProgramOutcomeSet(
            `${args.poSetId}/outcomes/${args.outcomeId}/`,
            args.body,
            'PATCH',
          )
        : changeProgramOutcomeSet(`${args.poSetId}/outcomes/`, args.body, 'POST'),
    onSuccess: async () => {
      setEditingOutcome(null);
      setAddingOutcomeOpen(false);
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-set-outcomes', activeSet?.id ?? null],
      });
    },
  });

  function handleCreateDraftSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProgramId) return;
    const data = new FormData(event.currentTarget);
    createDraftMutation.mutate({
      program: activeProgramId,
      effective_date: String(data.get('effective_date') ?? '').trim(),
      source_reference: String(data.get('source_reference') ?? '').trim(),
    });
  }

  function handleSaveOutcomeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeSet) return;
    const data = new FormData(event.currentTarget);
    saveOutcomeMutation.mutate({
      poSetId: activeSet.id,
      outcomeId: editingOutcome?.id,
      body: {
        code: String(data.get('code') ?? '').trim(),
        label: String(data.get('label') ?? '').trim(),
        description: String(data.get('description') ?? '').trim(),
        source_reference: String(data.get('source_reference') ?? '').trim(),
        order: Number(data.get('order') ?? outcomes.length + 1),
      },
    });
  }

  if (workspaceQuery.isPending) {
    return (
      <div className="space-y-4" role="status">
        <p className="text-sm text-muted-foreground">
          Loading PO1–PO11 set versions…
        </p>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (workspaceQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Unable to load PO sets</AlertTitle>
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

  const lifecycle = activeSet ? resolvePoSetLifecycle(activeSet) : null;
  const isDraft = lifecycle === 'draft';

  return (
    <div className="space-y-6">
      {/* Program Scope & Primary Action */}
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)]">
        <Field className="min-w-[260px] max-w-md flex-1">
          <FieldLabel htmlFor={programSelectId}>Program scope</FieldLabel>
          <NativeSelect
            id={programSelectId}
            value={activeProgramId}
            onChange={(e) => {
              setSelectedProgramId(e.target.value);
              setSelectedSetId('');
            }}
          >
            {programs.map((program) => (
              <NativeSelectOption key={program.id} value={program.id}>
                {program.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <Button type="button" onClick={() => setCreateDraftOpen(true)}>
          <Plus className="size-4" aria-hidden="true" />
          New draft PO set
        </Button>
      </div>

      {poSetsQuery.isError && (
        <Alert variant="destructive">
          <AlertTitle>Unable to load program outcome sets</AlertTitle>
          <AlertDescription>{errorMessage(poSetsQuery.error)}</AlertDescription>
        </Alert>
      )}

      {/* Version Strip */}
      {poSetsQuery.isPending ? (
        <Skeleton className="h-28 w-full" />
      ) : poSets.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No PO sets configured</EmptyTitle>
            <EmptyDescription>
              Create a draft PO1–PO11 set to define authoritative program
              outcomes for this degree program.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="grid gap-3 md:grid-cols-3" role="listbox" aria-label="PO set versions">
          {poSets.map((set) => {
            const isSelected = activeSet?.id === set.id;
            return (
              <button
                key={set.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => setSelectedSetId(set.id)}
                className={`rounded-[var(--radius-card,10px)] border p-4 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring ${
                  isSelected
                    ? 'border-[var(--accent-border)] bg-[var(--accent-soft)]'
                    : 'border-border bg-card hover:bg-[var(--surface-hover)]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="tabular-mono text-sm font-semibold text-foreground">
                    PO-Set v{set.version}
                  </span>
                  <PoSetStatusBadge poSet={set} />
                </div>
                <p className="mt-2 truncate text-xs text-muted-foreground">
                  {set.source_reference || 'No source reference'}
                </p>
                <p className="tabular-mono mt-1 text-[11px] text-muted-foreground">
                  Effective: {set.effective_date ?? 'Unscheduled'}
                  {set.activated_at
                    ? ` · Activated ${set.activated_at.slice(0, 10)}`
                    : ''}
                </p>
              </button>
            );
          })}
        </div>
      )}

      {/* Active Selected PO Set Ledger */}
      {activeSet && (
        <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
          <CardHeader className="border-b border-border/70 pb-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle>
                    <h2 className="text-lg font-semibold tracking-tight">
                      PO-Set v{activeSet.version} authoritative outcomes
                    </h2>
                  </CardTitle>
                  <PoSetStatusBadge poSet={activeSet} />
                </div>
                <CardDescription>
                  Source: {activeSet.source_reference || '—'} · Effective date:{' '}
                  <span className="tabular-mono">
                    {activeSet.effective_date ?? 'Pending activation'}
                  </span>
                </CardDescription>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {isDraft ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setEditingOutcome(null);
                        setAddingOutcomeOpen(true);
                      }}
                    >
                      <Plus className="size-4" aria-hidden="true" />
                      Add outcome
                    </Button>
                    <Button
                      type="button"
                      onClick={() => {
                        setActivateEffectiveDate(
                          activeSet.effective_date ??
                            new Date().toISOString().slice(0, 10),
                        );
                        setActivateDialogOpen(true);
                      }}
                      disabled={outcomes.length === 0}
                    >
                      <ShieldCheck className="size-4" aria-hidden="true" />
                      Activate PO-Set v{activeSet.version}
                    </Button>
                  </>
                ) : (
                  <Badge
                    variant="secondary"
                    className="inline-flex items-center gap-1.5"
                  >
                    <Lock className="size-3" aria-hidden="true" />
                    Immutable {lifecycle === 'active' ? 'active' : 'archived'}{' '}
                    version
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4 pt-5">
            {activateMutation.isError && (
              <Alert variant="destructive">
                <AlertTitle>Activation failed</AlertTitle>
                <AlertDescription>
                  {errorMessage(activateMutation.error)}
                </AlertDescription>
              </Alert>
            )}

            {outcomesQuery.isPending ? (
              <div className="space-y-2" role="status">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-44 w-full" />
              </div>
            ) : outcomesQuery.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Unable to load outcomes</AlertTitle>
                <AlertDescription>
                  {errorMessage(outcomesQuery.error)}
                </AlertDescription>
              </Alert>
            ) : outcomes.length === 0 ? (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>No outcomes in this draft set</EmptyTitle>
                  <EmptyDescription>
                    Add PO1–PO11 authoritative descriptions before activating
                    this PO set.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
                <Table>
                  <TableCaption className="pb-3">
                    Authoritative Program Outcomes for PO-Set v
                    {activeSet.version} ({lifecycle}).
                  </TableCaption>
                  <TableHeader className="bg-[var(--surface-subtle)]">
                    <TableRow>
                      <TableHead scope="col">Code</TableHead>
                      <TableHead scope="col">Label</TableHead>
                      <TableHead scope="col">Authoritative description</TableHead>
                      <TableHead scope="col">Source reference</TableHead>
                      {isDraft && (
                        <TableHead scope="col" className="text-right">
                          Action
                        </TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {outcomes.map((outcome) => (
                      <TableRow key={outcome.id}>
                        <th
                          scope="row"
                          className="tabular-mono p-2.5 text-left align-top font-semibold whitespace-nowrap"
                        >
                          {outcome.code}
                        </th>
                        <TableCell className="align-top font-medium">
                          {outcome.label}
                        </TableCell>
                        <TableCell className="max-w-xl align-top text-sm text-muted-foreground">
                          {outcome.description}
                        </TableCell>
                        <TableCell className="align-top text-xs text-muted-foreground">
                          {outcome.source_reference || '—'}
                        </TableCell>
                        {isDraft && (
                          <TableCell className="align-top text-right">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingOutcome(outcome)}
                            >
                              <Pencil className="size-3.5" aria-hidden="true" />
                              Edit
                            </Button>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Create New Draft PO Set Dialog */}
      <Dialog open={createDraftOpen} onOpenChange={setCreateDraftOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create new draft PO set</DialogTitle>
            <DialogDescription>
              Draft PO sets can be edited freely until activation. Activating a
              new version archives the currently active PO set without modifying
              historical publications.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateDraftSubmit} className="space-y-4">
            <FieldGroup>
              <Field>
                <FieldLabel>
                  Planned effective date
                  <Input
                    name="effective_date"
                    type="date"
                    required
                    defaultValue={new Date().toISOString().slice(0, 10)}
                  />
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>
                  Source reference
                  <Input
                    name="source_reference"
                    required
                    placeholder="e.g. MÜDEK / ABET 2026-2027 Senate Decision"
                  />
                </FieldLabel>
              </Field>
            </FieldGroup>
            {createDraftMutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {errorMessage(createDraftMutation.error)}
                </AlertDescription>
              </Alert>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateDraftOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createDraftMutation.isPending}>
                {createDraftMutation.isPending ? 'Creating…' : 'Create draft'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add / Edit Outcome Dialog (Draft Only) */}
      <Dialog
        open={Boolean(editingOutcome) || addingOutcomeOpen}
        onOpenChange={(open) => {
          if (!open) {
            setEditingOutcome(null);
            setAddingOutcomeOpen(false);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingOutcome
                ? `Edit ${editingOutcome.code}`
                : 'Add program outcome'}
            </DialogTitle>
            <DialogDescription>
              Authoritative text is frozen upon PO-set activation and quoted in
              student profiles and accreditation exports.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSaveOutcomeSubmit} className="space-y-4">
            <FieldGroup>
              <Field>
                <FieldLabel>
                  Code
                  <Input
                    name="code"
                    required
                    defaultValue={editingOutcome?.code ?? `PO${outcomes.length + 1}`}
                  />
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>
                  Short label
                  <Input
                    name="label"
                    required
                    defaultValue={editingOutcome?.label ?? ''}
                  />
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>
                  Authoritative description
                  <Input
                    name="description"
                    required
                    defaultValue={editingOutcome?.description ?? ''}
                  />
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>
                  Source reference
                  <Input
                    name="source_reference"
                    defaultValue={
                      editingOutcome?.source_reference ??
                      activeSet?.source_reference ??
                      ''
                    }
                  />
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel>
                  Order
                  <Input
                    name="order"
                    type="number"
                    min="1"
                    required
                    defaultValue={editingOutcome?.order ?? outcomes.length + 1}
                  />
                </FieldLabel>
              </Field>
            </FieldGroup>
            {saveOutcomeMutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {errorMessage(saveOutcomeMutation.error)}
                </AlertDescription>
              </Alert>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditingOutcome(null);
                  setAddingOutcomeOpen(false);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saveOutcomeMutation.isPending}>
                {saveOutcomeMutation.isPending ? 'Saving…' : 'Save outcome'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Activate Immutability Confirmation Dialog */}
      <Dialog open={activateDialogOpen} onOpenChange={setActivateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Activate PO-Set v{activeSet?.version} permanently?
            </DialogTitle>
            <DialogDescription>
              Activating this PO set permanently locks all {outcomes.length}{' '}
              outcome descriptions and archives the previously active set.
              Publications created under different PO-Set versions can never be
              blended in trend comparisons.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Field>
              <FieldLabel>
                Effective date
                <Input
                  type="date"
                  value={activateEffectiveDate}
                  onChange={(e) => setActivateEffectiveDate(e.target.value)}
                />
              </FieldLabel>
            </Field>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setActivateDialogOpen(false)}
              disabled={activateMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!activeSet || activateMutation.isPending}
              onClick={() =>
                activeSet &&
                activateMutation.mutate({
                  id: activeSet.id,
                  effective_date: activateEffectiveDate || undefined,
                })
              }
            >
              <CheckCircle2 className="size-4" aria-hidden="true" />
              {activateMutation.isPending
                ? 'Activating…'
                : `Confirm activate v${activeSet?.version}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
