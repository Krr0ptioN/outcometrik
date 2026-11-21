'use client';

import { memo } from 'react';
import {
  MeasuredZeroTag,
  NotAssessedText,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import { formatCoveragePercent, shortRef } from '../api';
import type { CohortOutcomeMetric } from '../types';
import {
  formatExclusionParts,
  formatMinMax,
  isMeasuredZero,
} from './cohort-formatters';

export interface CohortSummaryTableProps {
  publicationId: string;
  poSetVersion: number;
  outcomes: CohortOutcomeMetric[];
}

export const CohortSummaryTable = memo(function CohortSummaryTable({
  publicationId,
  poSetVersion,
  outcomes,
}: CohortSummaryTableProps) {
  return (
    <section
      aria-labelledby="po-distribution-table-title"
      className="space-y-2"
    >
      <h3
        id="po-distribution-table-title"
        className="text-base font-semibold tracking-tight"
      >
        Cohort PO summary table
      </h3>
      <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
        <Table>
          <TableCaption className="pb-3">
            Published cohort PO attainment (0–100 scale), sample size, coverage,
            and missing exclusions for Publication {shortRef(publicationId)}{' '}
            (PO-Set v{poSetVersion}).
          </TableCaption>
          <TableHeader className="bg-[var(--surface-subtle)]">
            <TableRow>
              <TableHead scope="col">PO code</TableHead>
              <TableHead scope="col" className="text-right">
                Mean (0–100)
              </TableHead>
              <TableHead scope="col" className="text-right">
                Median
              </TableHead>
              <TableHead scope="col" className="text-right">
                Min–Max
              </TableHead>
              <TableHead scope="col" className="text-right">
                Sample size (n / population)
              </TableHead>
              <TableHead scope="col" className="text-right">
                Coverage (%)
              </TableHead>
              <TableHead scope="col">
                Buckets (&lt;50 / 50–69.9 / 70–84.9 / 85–100)
              </TableHead>
              <TableHead scope="col">Missing / Excluded</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {outcomes.map((outcome) => {
              const exclusionParts = formatExclusionParts(outcome.exclusions);
              return (
                <TableRow
                  key={outcome.code}
                  className="transition-colors duration-150 hover:bg-[var(--surface-hover)]"
                >
                  <th
                    scope="row"
                    className="p-2.5 text-left align-middle font-medium whitespace-nowrap"
                  >
                    <span className="tabular-mono">{outcome.code}</span>
                    <span
                      className="block max-w-[240px] truncate text-xs font-normal text-muted-foreground"
                      title={outcome.label}
                    >
                      {outcome.label}
                    </span>
                  </th>
                  <TableCell className="tabular-mono text-right">
                    {outcome.n === 0 || outcome.mean === null ? (
                      <NotAssessedText />
                    ) : isMeasuredZero(outcome) ? (
                      <MeasuredZeroTag value="0.0" />
                    ) : (
                      outcome.mean
                    )}
                  </TableCell>
                  <TableCell className="tabular-mono text-right">
                    {outcome.n > 0 && outcome.median !== null
                      ? outcome.median
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-mono text-right">
                    {formatMinMax(outcome)}
                  </TableCell>
                  <TableCell className="tabular-mono text-right">
                    {outcome.n} / {outcome.population_size}
                  </TableCell>
                  <TableCell className="tabular-mono text-right">
                    {formatCoveragePercent(outcome.coverage)}
                  </TableCell>
                  <TableCell className="tabular-mono whitespace-nowrap">
                    {outcome.distribution['<50']} /{' '}
                    {outcome.distribution['50-69.9']} /{' '}
                    {outcome.distribution['70-84.9']} /{' '}
                    {outcome.distribution['85-100']}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {exclusionParts.length > 0
                      ? exclusionParts.join(', ')
                      : 'None'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </section>
  );
});
