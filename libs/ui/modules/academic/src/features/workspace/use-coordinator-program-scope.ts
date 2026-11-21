'use client';

import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { getProgramOutcomeSets } from '../syllabus/api';
import { getCoordinatorWorkspace } from './api';

/**
 * Shared custom hook encapsulating coordinator program scope selection,
 * authorized programs/offerings, and versioned PO-sets for the active program.
 * Eliminates duplicated workspace + program + PO-set query boilerplate across
 * coordinator governance organisms.
 */
export function useCoordinatorProgramScope() {
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

  const poSets = useMemo(
    () => [...(poSetsQuery.data ?? [])].sort((a, b) => b.version - a.version),
    [poSetsQuery.data],
  );

  const activePoSet = useMemo(
    () => poSets.find((s) => s.active) ?? poSets[0] ?? null,
    [poSets],
  );

  return {
    workspaceQuery,
    programs,
    offerings,
    activeProgramId,
    setSelectedProgramId,
    poSetsQuery,
    poSets,
    activePoSet,
  };
}
