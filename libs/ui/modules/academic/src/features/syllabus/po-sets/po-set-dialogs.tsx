'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
} from '@outcometrik/ui';
import {
  changeProgramOutcomeSet,
  type ProgramOutcome,
  type ProgramOutcomeSet,
} from '../api';

export function CreateDraftPoSetDialog({
  open,
  onOpenChange,
  programId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  programId: string;
}) {
  const queryClient = useQueryClient();
  const createDraftMutation = useMutation({
    mutationFn: (payload: {
      program: string;
      effective_date: string;
      source_reference: string;
    }) => changeProgramOutcomeSet('', payload, 'POST'),
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-sets', programId],
      });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!programId) return;
    const data = new FormData(event.currentTarget);
    createDraftMutation.mutate({
      program: programId,
      effective_date: String(data.get('effective_date') ?? '').trim(),
      source_reference: String(data.get('source_reference') ?? '').trim(),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create new draft PO set</DialogTitle>
          <DialogDescription>
            Draft PO sets can be edited freely until activation. Activating a
            new version archives the currently active PO set without modifying
            historical publications.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
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
              onClick={() => onOpenChange(false)}
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
  );
}

export function EditOutcomeDialog({
  open,
  onClose,
  poSet,
  editingOutcome,
  nextOrder,
}: {
  open: boolean;
  onClose: () => void;
  poSet: ProgramOutcomeSet | null;
  editingOutcome: ProgramOutcome | null;
  nextOrder: number;
}) {
  const queryClient = useQueryClient();
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
      onClose();
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-set-outcomes', poSet?.id ?? null],
      });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!poSet) return;
    const data = new FormData(event.currentTarget);
    saveOutcomeMutation.mutate({
      poSetId: poSet.id,
      outcomeId: editingOutcome?.id,
      body: {
        code: String(data.get('code') ?? '').trim(),
        label: String(data.get('label') ?? '').trim(),
        description: String(data.get('description') ?? '').trim(),
        source_reference: String(data.get('source_reference') ?? '').trim(),
        order: Number(data.get('order') ?? nextOrder),
      },
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
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
        <form onSubmit={handleSubmit} className="space-y-4">
          <FieldGroup>
            <Field>
              <FieldLabel>
                Code
                <Input
                  name="code"
                  required
                  defaultValue={editingOutcome?.code ?? `PO${nextOrder}`}
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
                    poSet?.source_reference ??
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
                  defaultValue={editingOutcome?.order ?? nextOrder}
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
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saveOutcomeMutation.isPending}>
              {saveOutcomeMutation.isPending ? 'Saving…' : 'Save outcome'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ActivatePoSetDialog({
  open,
  onOpenChange,
  programId,
  poSet,
  outcomeCount,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  programId: string;
  poSet: ProgramOutcomeSet | null;
  outcomeCount: number;
}) {
  const queryClient = useQueryClient();
  const [effectiveDate, setEffectiveDate] = useState<string>(
    () => poSet?.effective_date ?? new Date().toISOString().slice(0, 10),
  );

  const activateMutation = useMutation({
    mutationFn: (args: { id: string; effective_date?: string }) =>
      changeProgramOutcomeSet(
        `${args.id}/activate/`,
        args.effective_date ? { effective_date: args.effective_date } : {},
        'POST',
      ),
    onSuccess: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'po-sets', programId],
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Activate PO-Set v{poSet?.version} permanently?</DialogTitle>
          <DialogDescription>
            Activating this PO set permanently locks all {outcomeCount} outcome
            descriptions and archives the previously active set. Publications
            created under different PO-Set versions can never be blended in
            trend comparisons.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <Field>
            <FieldLabel>
              Effective date
              <Input
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
              />
            </FieldLabel>
          </Field>
          {activateMutation.isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {errorMessage(activateMutation.error)}
              </AlertDescription>
            </Alert>
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={activateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!poSet || activateMutation.isPending}
            onClick={() =>
              poSet &&
              activateMutation.mutate({
                id: poSet.id,
                effective_date: effectiveDate || undefined,
              })
            }
          >
            <CheckCircle2 className="size-4" aria-hidden="true" />
            {activateMutation.isPending
              ? 'Activating…'
              : `Confirm activate v${poSet?.version}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
