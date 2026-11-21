'use client';

import { memo } from 'react';
import { ArrowUpRight } from 'lucide-react';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  AlertTitle,
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
  Skeleton,
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
import {
  resolvePublicationFreshness,
  type GovernancePublication,
} from '../publications-api';

function shortHash(hash: string): string {
  return hash.length > 12 ? hash.slice(0, 12) : hash;
}

export interface PublicationSeriesTableProps {
  publications: GovernancePublication[];
  isPending: boolean;
  error: unknown;
}

export const PublicationSeriesTable = memo(function PublicationSeriesTable({
  publications,
  isPending,
  error,
}: PublicationSeriesTableProps) {
  return (
    <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle>
          <h2 className="text-lg font-semibold tracking-tight">
            Immutable publication series
          </h2>
        </CardTitle>
        <CardDescription>
          Historical and current snapshots with cryptographic input manifest
          hashes. Publishing a new series clears STALE status without altering
          prior series.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-5">
        {isPending ? (
          <div className="space-y-2" role="status">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <AlertTitle>Unable to load publications</AlertTitle>
            <AlertDescription>{errorMessage(error)}</AlertDescription>
          </Alert>
        ) : publications.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>No publications yet</EmptyTitle>
              <EmptyDescription>
                Run calculation and publish Series v1 to create the first
                immutable outcome snapshot for this program.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="overflow-x-auto rounded-[var(--radius-card,10px)] border border-border">
            <Table>
              <TableCaption className="pb-3">
                Immutable publication series for the selected program.
              </TableCaption>
              <TableHeader className="bg-[var(--surface-subtle)]">
                <TableRow>
                  <TableHead scope="col">Series</TableHead>
                  <TableHead scope="col">Scope &amp; term</TableHead>
                  <TableHead scope="col">PO-Set</TableHead>
                  <TableHead scope="col">Audience</TableHead>
                  <TableHead scope="col">Freshness</TableHead>
                  <TableHead scope="col">Published at</TableHead>
                  <TableHead scope="col">Manifest hash</TableHead>
                  <TableHead scope="col" className="text-right">
                    Inspect
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {publications.map((pub) => {
                  const freshness = resolvePublicationFreshness(
                    pub,
                    publications,
                  );
                  return (
                    <TableRow key={pub.id}>
                      <th
                        scope="row"
                        className="tabular-mono p-2.5 text-left align-middle font-semibold whitespace-nowrap"
                      >
                        Series v{pub.series_version}
                        <span className="block text-[11px] font-normal text-muted-foreground">
                          {pub.id.slice(0, 8)}
                        </span>
                      </th>
                      <TableCell className="text-xs">
                        <span className="font-medium">
                          {pub.offering_label ?? 'Program cumulative'}
                        </span>
                        <span className="block text-muted-foreground">
                          {pub.term_label ?? 'All terms'}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-mono text-xs">
                        PO-Set v{pub.po_set_version}
                      </TableCell>
                      <TableCell className="text-xs capitalize">
                        {pub.audience}
                      </TableCell>
                      <TableCell>
                        {freshness === 'current' ? (
                          <StatusDot variant="success" label="Current" />
                        ) : freshness === 'stale' ? (
                          <StaleTag label="Stale" />
                        ) : (
                          <StatusDot variant="neutral" label="Historical" />
                        )}
                      </TableCell>
                      <TableCell className="tabular-mono text-xs text-muted-foreground whitespace-nowrap">
                        {pub.published_at
                          ? pub.published_at.slice(0, 16).replace('T', ' ')
                          : '—'}
                      </TableCell>
                      <TableCell
                        className="tabular-mono text-xs text-muted-foreground"
                        title={pub.input_hash}
                      >
                        {shortHash(pub.input_hash)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button asChild variant="ghost" size="sm">
                          <a
                            href={`/coordinator/analytics?program=${encodeURIComponent(pub.program)}&publication=${encodeURIComponent(pub.id)}`}
                          >
                            Analytics
                            <ArrowUpRight
                              className="size-3.5"
                              aria-hidden="true"
                            />
                          </a>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
});
