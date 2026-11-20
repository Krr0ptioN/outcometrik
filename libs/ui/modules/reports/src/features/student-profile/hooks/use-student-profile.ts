'use client';

import { useQuery } from '@tanstack/react-query';
import { getStudentPublicationScores, getStudentPublications } from '../api';

export const studentProfileKeys = {
  publications: () => ['reports', 'student-publications'] as const,
  scores: (publicationId: string | null) =>
    ['reports', 'student-publication-scores', publicationId] as const,
};

export function useStudentPublications() {
  return useQuery({
    queryKey: studentProfileKeys.publications(),
    queryFn: ({ signal }) => getStudentPublications(signal),
  });
}

export function useStudentPublicationScores(publicationId: string | null) {
  return useQuery({
    queryKey: studentProfileKeys.scores(publicationId),
    queryFn: ({ signal }) =>
      getStudentPublicationScores(publicationId as string, signal),
    enabled: Boolean(publicationId),
  });
}
