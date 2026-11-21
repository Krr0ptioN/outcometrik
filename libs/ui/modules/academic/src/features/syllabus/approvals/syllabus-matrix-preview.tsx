'use client';

import { memo } from 'react';
import { CheckCircle2, ShieldAlert } from 'lucide-react';
import {
  Skeleton,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import type {
  ProgramOutcome,
  Syllabus,
  SyllabusMappingValidation,
} from '../api';

export interface SyllabusMatrixPreviewProps {
  syllabus: Syllabus;
  programOutcomes: ProgramOutcome[];
  validation: SyllabusMappingValidation | undefined;
  validationPending: boolean;
}

export const SyllabusMatrixPreview = memo(function SyllabusMatrixPreview({
  syllabus,
  programOutcomes,
  validation,
  validationPending,
}: SyllabusMatrixPreviewProps) {
  return (
    <div className="space-y-5">
      {validationPending ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        validation && (
          <div
            className={`rounded-[var(--radius-card,10px)] border p-3.5 text-sm ${
              validation.is_valid_for_approval
                ? 'border-[var(--status-success-border)] bg-[var(--status-success-bg)]/60'
                : 'border-[var(--status-danger-border)] bg-[var(--status-danger-bg)]/60'
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-2 font-medium">
                {validation.is_valid_for_approval ? (
                  <>
                    <CheckCircle2
                      className="size-4 text-[var(--status-success-fg)]"
                      aria-hidden="true"
                    />
                    Ready for approval — all mapping rules satisfied
                  </>
                ) : (
                  <>
                    <ShieldAlert
                      className="size-4 text-[var(--status-danger-fg)]"
                      aria-hidden="true"
                    />
                    Validation blockers must be resolved before locking
                  </>
                )}
              </span>
              <span className="tabular-mono text-xs text-muted-foreground">
                Mapped LOs:{' '}
                {
                  validation.lo_statuses.filter((l) => l.status === 'MAPPED')
                    .length
                }
                /{validation.lo_statuses.length} · Assessed POs:{' '}
                {
                  validation.po_statuses.filter((p) => p.status === 'ASSESSED')
                    .length
                }
                /{validation.po_statuses.length}
              </span>
            </div>
            {validation.errors.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--status-danger-fg)]">
                {validation.errors.map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )
      )}

      {/* A×LO Matrix Preview */}
      <section className="space-y-2">
        <h4 className="text-sm font-semibold">
          Assessment × Learning Outcome (A×LO) matrix preview
        </h4>
        <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
          <Table>
            <TableCaption className="pb-2">
              A×LO weights for syllabus v{syllabus.version}.
            </TableCaption>
            <TableHeader className="bg-[var(--surface-subtle)]">
              <TableRow>
                <TableHead scope="col">Assessment</TableHead>
                {syllabus.learning_outcomes.map((lo) => (
                  <TableHead
                    key={lo.id}
                    scope="col"
                    className="tabular-mono text-right"
                  >
                    {lo.code}
                  </TableHead>
                ))}
                <TableHead scope="col" className="text-right">
                  Row sum
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {syllabus.assessments.map((assessment) => {
                const rowMappings = (
                  syllabus.assessment_lo_mappings ?? []
                ).filter((m) => m.assessment === assessment.id && m.is_active);
                const rowSum = rowMappings.reduce(
                  (acc, m) => acc + Number(m.weight || 0),
                  0,
                );
                return (
                  <TableRow key={assessment.id}>
                    <th
                      scope="row"
                      className="p-2.5 text-left text-xs font-medium whitespace-nowrap"
                    >
                      <span className="tabular-mono">{assessment.code}</span>{' '}
                      <span className="text-muted-foreground">
                        ({assessment.kind}, max {assessment.max_points})
                      </span>
                    </th>
                    {syllabus.learning_outcomes.map((lo) => {
                      const cell = rowMappings.find(
                        (m) => m.learning_outcome === lo.id,
                      );
                      return (
                        <TableCell
                          key={lo.id}
                          className="tabular-mono text-right text-xs"
                        >
                          {cell ? cell.weight : '—'}
                        </TableCell>
                      );
                    })}
                    <TableCell className="tabular-mono text-right text-xs font-semibold">
                      {rowSum.toFixed(2)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* LO×PO Matrix Preview */}
      <section className="space-y-2">
        <h4 className="text-sm font-semibold">
          Learning Outcome × Program Outcome (LO×PO) matrix preview
        </h4>
        <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
          <Table>
            <TableCaption className="pb-2">
              LO×PO mapping weights (1–5) for syllabus v{syllabus.version}.
            </TableCaption>
            <TableHeader className="bg-[var(--surface-subtle)]">
              <TableRow>
                <TableHead scope="col">Learning outcome</TableHead>
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
              {syllabus.learning_outcomes.map((lo) => {
                const rowMappings = (syllabus.lo_po_mappings ?? []).filter(
                  (m) => m.learning_outcome === lo.id && m.is_active,
                );
                return (
                  <TableRow key={lo.id}>
                    <th
                      scope="row"
                      className="p-2.5 text-left text-xs font-medium"
                    >
                      <span className="tabular-mono">{lo.code}</span>
                      <span className="block max-w-[220px] truncate font-normal text-muted-foreground">
                        {lo.description}
                      </span>
                    </th>
                    {programOutcomes.map((po) => {
                      const cell = rowMappings.find(
                        (m) => m.program_outcome === po.id,
                      );
                      return (
                        <TableCell
                          key={po.id}
                          className="tabular-mono text-center text-xs"
                        >
                          {cell ? (
                            <span className="inline-flex size-6 items-center justify-center rounded-[4px] bg-[var(--accent-soft)] font-semibold text-[var(--accent-primary)]">
                              {cell.weight}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
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
      </section>
    </div>
  );
});
