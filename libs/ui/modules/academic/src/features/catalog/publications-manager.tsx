'use client';

import { useQuery } from '@tanstack/react-query';
import { useId, useMemo, useState } from 'react';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
  Skeleton,
} from '@outcometrik/ui';
import { getAllSyllabi, getProgramOutcomeSets } from '../syllabus/api';
import { getCoordinatorWorkspace } from '../workspace/api';
import { getCatalogRows } from './api';
import {
  getCalculationRuns,
  getProgramPublications,
  type CalculationRun,
} from './publications-api';
import { PublicationSeriesTable } from './publications/publication-series-table';
import { ReadinessGatesCard } from './publications/readiness-gates-card';
import { RunPublishCard } from './publications/run-publish-card';

export function CoordinatorPublicationsManager() {
  const programSelectId = useId();
  const [selectedProgramId, setSelectedProgramId] = useState<string>('');

  const workspaceQuery = useQuery({
    queryKey: ['academic', 'coordinator'],
    queryFn: ({ signal }) => getCoordinatorWorkspace(signal),
  });

  const programs = useMemo(
    () => workspaceQuery.data?.programs ?? [],
    [workspaceQuery.data],
  );
  const offerings = useMemo(
    () => workspaceQuery.data?.offerings ?? [],
    [workspaceQuery.data],
  );

  const activeProgramId =
    selectedProgramId && programs.some((p) => p.id === selectedProgramId)
      ? selectedProgramId
      : (programs[0]?.id ?? '');

  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', activeProgramId],
    queryFn: ({ signal }) => getProgramOutcomeSets(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const syllabiQuery = useQuery({
    queryKey: ['academic', 'syllabi', 'all'],
    queryFn: ({ signal }) => getAllSyllabi(undefined, signal),
    enabled: Boolean(activeProgramId),
  });

  const termsQuery = useQuery({
    queryKey: ['academic', 'terms', 'all'],
    queryFn: ({ signal }) => getCatalogRows('terms', {}, signal),
    enabled: Boolean(activeProgramId),
  });

  const runsQuery = useQuery({
    queryKey: ['academic', 'calculation-runs', activeProgramId],
    queryFn: ({ signal }) => getCalculationRuns(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const publicationsQuery = useQuery({
    queryKey: ['academic', 'publications', activeProgramId],
    queryFn: ({ signal }) => getProgramPublications(activeProgramId, signal),
    enabled: Boolean(activeProgramId),
  });

  const activePoSet = useMemo(
    () => (poSetsQuery.data ?? []).find((s) => s.active) ?? null,
    [poSetsQuery.data],
  );

  const syllabusReadiness = useMemo(() => {
    const programOfferings = offerings.filter(
      (o) => o.program_id === activeProgramId,
    );
    const allSyllabi = syllabiQuery.data ?? [];
    let approvedOfferings = 0;
    let draftOnlyOfferings = 0;
    for (const off of programOfferings) {
      const offSyllabi = allSyllabi.filter((s) => s.offering === off.id);
      if (offSyllabi.some((s) => s.status === 'approved')) {
        approvedOfferings += 1;
      } else if (offSyllabi.some((s) => s.status === 'draft')) {
        draftOnlyOfferings += 1;
      }
    }
    return {
      totalOfferings: programOfferings.length,
      approvedOfferings,
      draftOnlyOfferings,
    };
  }, [offerings, activeProgramId, syllabiQuery.data]);

  const latestRun: CalculationRun | null = useMemo(() => {
    const programRuns = (runsQuery.data ?? []).filter(
      (r) => r.scope_kind === 'program',
    );
    if (programRuns.length === 0) return null;
    return programRuns.reduce((latest, run) =>
      run.created_at > latest.created_at ? run : latest,
    );
  }, [runsQuery.data]);

  const publications = useMemo(
    () =>
      [...(publicationsQuery.data ?? [])].sort((a, b) => {
        if (b.series_version !== a.series_version) {
          return b.series_version - a.series_version;
        }
        return (b.published_at ?? '').localeCompare(a.published_at ?? '');
      }),
    [publicationsQuery.data],
  );

  const terms = useMemo(
    () =>
      (termsQuery.data ?? []).map((t) => ({
        id: t.id,
        label: `${String(t.year ?? '')} ${String(t.season ?? '').replace(/^./, (c) => c.toUpperCase())}`.trim(),
      })),
    [termsQuery.data],
  );

  if (workspaceQuery.isPending) {
    return (
      <div className="space-y-4" role="status">
        <p className="text-sm text-muted-foreground">
          Loading calculation runs and publications…
        </p>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (workspaceQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Unable to load publications workspace</AlertTitle>
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)]">
        <Field className="min-w-[260px] max-w-md flex-1">
          <FieldLabel htmlFor={programSelectId}>Program scope</FieldLabel>
          <NativeSelect
            id={programSelectId}
            value={activeProgramId}
            onChange={(e) => setSelectedProgramId(e.target.value)}
          >
            {programs.map((program) => (
              <NativeSelectOption key={program.id} value={program.id}>
                {program.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {activePoSet && (
            <Badge variant="secondary" className="tabular-mono">
              Active PO-Set v{activePoSet.version}
            </Badge>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ReadinessGatesCard
          activePoSet={activePoSet}
          totalOfferings={syllabusReadiness.totalOfferings}
          approvedOfferings={syllabusReadiness.approvedOfferings}
          draftOnlyOfferings={syllabusReadiness.draftOnlyOfferings}
          latestRun={latestRun}
        />

        <RunPublishCard
          key={activeProgramId}
          programId={activeProgramId}
          hasActivePoSet={Boolean(activePoSet)}
          hasApprovedSyllabus={syllabusReadiness.approvedOfferings > 0}
          latestRun={latestRun}
          publications={publications}
          terms={terms}
        />
      </div>

      <PublicationSeriesTable
        publications={publications}
        isPending={publicationsQuery.isPending}
        error={publicationsQuery.isError ? publicationsQuery.error : null}
      />
    </div>
  );
}
