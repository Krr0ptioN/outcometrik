'use client';

import { memo } from 'react';
import {
  StaleTag,
  StatusDot,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import { formatCoveragePercent, shortRef } from '../../api';
import type { CohortTrendPoint } from '../../types';

export interface TrendsComparisonTableProps {
  poSetVersion: number;
  points: CohortTrendPoint[];
}

export const TrendsComparisonTable = memo(function TrendsComparisonTable({
  poSetVersion,
  points,
}: TrendsComparisonTableProps) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
      <Table>
        <TableCaption className="pb-3">
          Trend comparison across compatible publications for PO-Set v
          {poSetVersion}.
        </TableCaption>
        <TableHeader className="bg-[var(--surface-subtle)]">
          <TableRow>
            <TableHead scope="col">Snapshot</TableHead>
            <TableHead scope="col">PO-Set</TableHead>
            <TableHead scope="col">Status</TableHead>
            <TableHead scope="col" className="text-right">
              Sample (n / population)
            </TableHead>
            <TableHead scope="col" className="text-right">
              Coverage
            </TableHead>
            <TableHead scope="col">PO means</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {points.map((point) => (
            <TableRow key={point.publication_id}>
              <th
                scope="row"
                className="p-2.5 text-left align-middle font-medium whitespace-nowrap"
              >
                {point.term?.label ?? shortRef(point.publication_id)}
                <span className="tabular-mono block text-xs font-normal text-muted-foreground">
                  Pub {shortRef(point.publication_id)} · Series v
                  {point.series_version}
                </span>
              </th>
              <TableCell className="tabular-mono">
                v{point.po_set_version}
              </TableCell>
              <TableCell>
                {point.publication_status === 'stale' ? (
                  <StaleTag label="Stale" />
                ) : (
                  <StatusDot variant="success" label="Published" />
                )}
              </TableCell>
              <TableCell className="tabular-mono text-right">
                {point.sample_size} / {point.population_size}
              </TableCell>
              <TableCell className="tabular-mono text-right">
                {formatCoveragePercent(point.coverage)}
              </TableCell>
              <TableCell className="tabular-mono text-xs">
                {point.outcomes
                  .map(
                    (o) =>
                      `${o.code}: ${o.n > 0 && o.mean !== null ? o.mean : '—'} (n=${o.n})`,
                  )
                  .join(' · ')}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
});
