'use client';

import { memo } from 'react';
import { Pencil } from 'lucide-react';
import {
  Button,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import type { ProgramOutcome } from '../api';

export interface PoSetLedgerTableProps {
  version: number;
  lifecycle: 'active' | 'archived' | 'draft';
  outcomes: ProgramOutcome[];
  isDraft: boolean;
  onEditOutcome: (outcome: ProgramOutcome) => void;
}

export const PoSetLedgerTable = memo(function PoSetLedgerTable({
  version,
  lifecycle,
  outcomes,
  isDraft,
  onEditOutcome,
}: PoSetLedgerTableProps) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
      <Table>
        <TableCaption className="pb-3">
          Authoritative Program Outcomes for PO-Set v{version} ({lifecycle}).
        </TableCaption>
        <TableHeader className="bg-[var(--surface-subtle)]">
          <TableRow>
            <TableHead scope="col">Code</TableHead>
            <TableHead scope="col">Label</TableHead>
            <TableHead scope="col">Authoritative description</TableHead>
            <TableHead scope="col">Source reference</TableHead>
            {isDraft ? (
              <TableHead scope="col" className="text-right">
                Action
              </TableHead>
            ) : null}
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
              {isDraft ? (
                <TableCell className="align-top text-right">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onEditOutcome(outcome)}
                  >
                    <Pencil className="size-3.5" aria-hidden="true" />
                    Edit
                  </Button>
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});
