'use client';

import { useQuery } from '@tanstack/react-query';
import {
  getCohortAnalytics,
  getCohortCourses,
  getCohortTerms,
  getCohortTrends,
  getCoordinatorPrograms,
  getCoordinatorPublications,
} from '../api';
import type { CohortAnalyticsParams, CohortTrendsParams } from '../types';

export function useCoordinatorProgramsQuery(enabled = true) {
  return useQuery({
    queryKey: ['reports', 'cohort-programs'],
    queryFn: ({ signal }) => getCoordinatorPrograms(signal),
    enabled,
  });
}

export function useCohortTermsQuery(enabled = true) {
  return useQuery({
    queryKey: ['reports', 'cohort-terms'],
    queryFn: ({ signal }) => getCohortTerms(signal),
    enabled,
  });
}

export function useCohortCoursesQuery(enabled = true) {
  return useQuery({
    queryKey: ['reports', 'cohort-courses'],
    queryFn: ({ signal }) => getCohortCourses(signal),
    enabled,
  });
}

export function useCoordinatorPublicationsQuery(
  programId: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ['reports', 'coordinator-publications', programId],
    queryFn: ({ signal }) => getCoordinatorPublications(programId ?? '', signal),
    enabled: enabled && Boolean(programId),
  });
}

export function useCohortAnalyticsQuery(
  params: CohortAnalyticsParams | null,
  enabled = true,
) {
  return useQuery({
    queryKey: [
      'reports',
      'cohort-analytics',
      params?.programId ?? null,
      params?.publicationId ?? null,
      params?.termId ?? null,
      params?.courseId ?? null,
    ],
    queryFn: ({ signal }) => {
      if (!params) {
        throw new Error('Cohort analytics parameters are required.');
      }
      return getCohortAnalytics(params, signal);
    },
    enabled: enabled && Boolean(params?.programId),
  });
}

export function useCohortTrendsQuery(
  params: CohortTrendsParams | null,
  enabled = false,
) {
  return useQuery({
    queryKey: [
      'reports',
      'cohort-trends',
      params?.programId ?? null,
      params?.poSetVersion ?? null,
      params?.publicationIds?.join(',') ?? null,
    ],
    queryFn: ({ signal }) => {
      if (!params) {
        throw new Error('Cohort trends parameters are required.');
      }
      return getCohortTrends(params, signal);
    },
    enabled: enabled && Boolean(params?.programId),
  });
}
