'use client';

import { useQuery } from '@tanstack/react-query';
import { useCallback, useId, useMemo, useState } from 'react';
import { Lock, Plus, ShieldCheck } from 'lucide-react';
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
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
  Skeleton,
  StatusDot,
} from '@outcometrik/ui';
import { getCoordinatorWorkspace } from '../workspace/api';
import {
  getProgramOutcomeSets,
  getProgramOutcomes,
  type ProgramOutcome,
  type ProgramOutcomeSet,
} from './api';
import {
  ActivatePoSetDialog,
  CreateDraftPoSetDialog,
  EditOutcomeDialog,
} from './po-sets/po-set-dialogs';
import { PoSetLedgerTable } from './po-sets/po-set-ledger-table';

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
  const [editingOutcome, setEditingOutcome] = useState<ProgramOutcome | null>(
    null,
  );
  const [addingOutcomeOpen, setAddingOutcomeOpen] = useState(false);

  const handleEditOutcome = useCallback((outcome: ProgramOutcome) => {
    setEditingOutcome(outcome);
  }, []);

  const handleCloseOutcomeDialog = useCallback(() => {
    setEditingOutcome(null);
    setAddingOutcomeOpen(false);
  }, []);

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
        <div
          className="grid gap-3 md:grid-cols-3"
          role="listbox"
          aria-label="PO set versions"
        >
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

      {activeSet && lifecycle && (
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
                      onClick={() => setActivateDialogOpen(true)}
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
              <PoSetLedgerTable
                version={activeSet.version}
                lifecycle={lifecycle}
                outcomes={outcomes}
                isDraft={isDraft}
                onEditOutcome={handleEditOutcome}
              />
            )}
          </CardContent>
        </Card>
      )}

      <CreateDraftPoSetDialog
        open={createDraftOpen}
        onOpenChange={setCreateDraftOpen}
        programId={activeProgramId}
      />

      <EditOutcomeDialog
        key={editingOutcome?.id ?? 'new'}
        open={Boolean(editingOutcome) || addingOutcomeOpen}
        onClose={handleCloseOutcomeDialog}
        poSet={activeSet}
        editingOutcome={editingOutcome}
        nextOrder={outcomes.length + 1}
      />

      <ActivatePoSetDialog
        key={activeSet?.id ?? 'none'}
        open={activateDialogOpen}
        onOpenChange={setActivateDialogOpen}
        programId={activeProgramId}
        poSet={activeSet}
        outcomeCount={outcomes.length}
      />
    </div>
  );
}
