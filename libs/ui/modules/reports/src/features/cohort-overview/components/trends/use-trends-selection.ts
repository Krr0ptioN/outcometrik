'use client';

import { useMemo } from 'react';
import { useCohortTrendsQuery } from '../../hooks/use-cohort-overview';
import { useCohortOverviewContext } from '../cohort-overview-context';
import { useTrendsStore } from './trends-store-context';

/**
 * Custom hook uniting `CohortOverviewContext`, `TrendsStore`, and the
 * `useCohortTrendsQuery` server query into derived snapshot selection state.
 */
export function useTrendsSelection() {
  const {
    activeProgramId: programId,
    publications,
    activePoSetVersion,
  } = useCohortOverviewContext();

  const customTrendPubIds = useTrendsStore((s) => s.customTrendPubIds);

  const compatibleIds = useMemo(
    () =>
      activePoSetVersion !== undefined
        ? publications
            .filter((p) => p.po_set_version === activePoSetVersion)
            .map((p) => p.id)
        : [],
    [publications, activePoSetVersion],
  );

  const publicationIdSet = useMemo(
    () => new Set(publications.map((pub) => pub.id)),
    [publications],
  );

  const selectedPublicationIds = useMemo(() => {
    if (customTrendPubIds !== null) {
      return customTrendPubIds.filter((id) => publicationIdSet.has(id));
    }
    return compatibleIds;
  }, [customTrendPubIds, publicationIdSet, compatibleIds]);

  const selectedIdSet = useMemo(
    () => new Set(selectedPublicationIds),
    [selectedPublicationIds],
  );

  const hasIncompatibleSelection = useMemo(() => {
    const versions = new Set<number>();
    for (const pub of publications) {
      if (selectedIdSet.has(pub.id)) {
        versions.add(pub.po_set_version);
      }
    }
    return versions.size > 1;
  }, [publications, selectedIdSet]);

  const trendsQuery = useCohortTrendsQuery(
    {
      programId,
      poSetVersion: customTrendPubIds === null ? activePoSetVersion : undefined,
      publicationIds:
        selectedPublicationIds.length > 0 ? selectedPublicationIds : undefined,
    },
    Boolean(programId),
  );

  return {
    publications,
    activePoSetVersion,
    compatibleIds,
    selectedIdSet,
    isCustomSelection: customTrendPubIds !== null,
    hasIncompatibleSelection,
    trendsQuery,
  };
}
