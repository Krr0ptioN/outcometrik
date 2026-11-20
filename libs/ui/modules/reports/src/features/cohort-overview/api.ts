import { ApiError, request } from '@outcometrik/api';
import type {
  CohortAnalyticsParams,
  CohortAnalyticsResponse,
  CohortCourseOption,
  CohortDistribution,
  CohortExclusions,
  CohortOutcomeMetric,
  CohortProgramOption,
  CohortTermOption,
  CohortTrendOutcome,
  CohortTrendPoint,
  CohortTrendsParams,
  CohortTrendsResponse,
  CohortTrendTerm,
  CoordinatorPublication,
  PublicationStatus,
} from './types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isStringOrNull(value: unknown): value is string | null {
  return typeof value === 'string' || value === null;
}

function isNonNegativeInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isPublicationStatus(value: unknown): value is PublicationStatus {
  return value === 'published' || value === 'stale';
}

function isCohortExclusions(value: unknown): value is CohortExclusions {
  return (
    isRecord(value) &&
    isNonNegativeInt(value.NOT_ASSESSED) &&
    isNonNegativeInt(value.INCOMPLETE) &&
    isNonNegativeInt(value.ALL_EXEMPT) &&
    isNonNegativeInt(value.UNMAPPED)
  );
}

function isCohortDistribution(value: unknown): value is CohortDistribution {
  return (
    isRecord(value) &&
    isNonNegativeInt(value['<50']) &&
    isNonNegativeInt(value['50-69.9']) &&
    isNonNegativeInt(value['70-84.9']) &&
    isNonNegativeInt(value['85-100'])
  );
}

function isCohortOutcomeMetric(value: unknown): value is CohortOutcomeMetric {
  return (
    isRecord(value) &&
    isStringOrNull(value.program_outcome_id) &&
    typeof value.code === 'string' &&
    typeof value.label === 'string' &&
    isNonNegativeInt(value.n) &&
    isNonNegativeInt(value.population_size) &&
    typeof value.coverage === 'string' &&
    isStringOrNull(value.mean) &&
    isStringOrNull(value.median) &&
    isStringOrNull(value.min) &&
    isStringOrNull(value.max) &&
    isCohortDistribution(value.distribution) &&
    isCohortExclusions(value.exclusions)
  );
}

function isCohortAnalyticsResponse(
  value: unknown,
): value is CohortAnalyticsResponse {
  return (
    isRecord(value) &&
    typeof value.publication_id === 'string' &&
    typeof value.run_id === 'string' &&
    isNonNegativeInt(value.series_version) &&
    typeof value.program_id === 'string' &&
    isStringOrNull(value.offering_id) &&
    isStringOrNull(value.term_id) &&
    isNonNegativeInt(value.po_set_version) &&
    typeof value.policy_version === 'string' &&
    typeof value.engine_version === 'string' &&
    isPublicationStatus(value.publication_status) &&
    typeof value.audience === 'string' &&
    isStringOrNull(value.published_at) &&
    isRecord(value.filters) &&
    isStringOrNull(value.filters.course_id) &&
    isStringOrNull(value.filters.term_id) &&
    isNonNegativeInt(value.sample_size) &&
    isNonNegativeInt(value.population_size) &&
    typeof value.coverage === 'string' &&
    isCohortExclusions(value.exclusions) &&
    Array.isArray(value.outcomes) &&
    value.outcomes.every(isCohortOutcomeMetric)
  );
}

function isCoordinatorPublication(
  value: unknown,
): value is CoordinatorPublication {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.program === 'string' &&
    isStringOrNull(value.offering) &&
    isStringOrNull(value.term) &&
    typeof value.run === 'string' &&
    isNonNegativeInt(value.series_version) &&
    isNonNegativeInt(value.po_set_version) &&
    typeof value.audience === 'string' &&
    isStringOrNull(value.published_at) &&
    typeof value.stale === 'boolean'
  );
}

function isCohortTrendTerm(value: unknown): value is CohortTrendTerm {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.year === 'number' &&
    typeof value.season === 'string' &&
    typeof value.label === 'string'
  );
}

function isCohortTrendOutcome(value: unknown): value is CohortTrendOutcome {
  return (
    isRecord(value) &&
    isStringOrNull(value.program_outcome_id) &&
    typeof value.code === 'string' &&
    typeof value.label === 'string' &&
    isStringOrNull(value.mean) &&
    isStringOrNull(value.median) &&
    isNonNegativeInt(value.n) &&
    isNonNegativeInt(value.population_size) &&
    typeof value.coverage === 'string' &&
    isCohortExclusions(value.exclusions)
  );
}

function isCohortTrendPoint(value: unknown): value is CohortTrendPoint {
  return (
    isRecord(value) &&
    typeof value.publication_id === 'string' &&
    typeof value.run_id === 'string' &&
    (value.term === null || isCohortTrendTerm(value.term)) &&
    isStringOrNull(value.term_id) &&
    isNonNegativeInt(value.po_set_version) &&
    isNonNegativeInt(value.series_version) &&
    typeof value.policy_version === 'string' &&
    isPublicationStatus(value.publication_status) &&
    isStringOrNull(value.published_at) &&
    isNonNegativeInt(value.sample_size) &&
    isNonNegativeInt(value.population_size) &&
    typeof value.coverage === 'string' &&
    isCohortExclusions(value.exclusions) &&
    Array.isArray(value.outcomes) &&
    value.outcomes.every(isCohortTrendOutcome)
  );
}

function isCohortTrendsResponse(value: unknown): value is CohortTrendsResponse {
  return (
    isRecord(value) &&
    typeof value.program_id === 'string' &&
    isNonNegativeInt(value.po_set_version) &&
    Array.isArray(value.points) &&
    value.points.every(isCohortTrendPoint)
  );
}

function extractResultsArray(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  if (isRecord(value) && Array.isArray(value.results)) return value.results;
  return null;
}

export async function getCoordinatorPublications(
  programId: string,
  signal?: AbortSignal,
): Promise<CoordinatorPublication[]> {
  const query = new URLSearchParams({ program: programId });
  const data: unknown = await request(`/api/v1/publications/?${query}`, {
    signal,
    cache: 'no-store',
  });
  const items = extractResultsArray(data);
  if (!items || !items.every(isCoordinatorPublication)) {
    throw new ApiError('unexpected', 200);
  }
  return items;
}

export async function getCohortAnalytics(
  params: CohortAnalyticsParams,
  signal?: AbortSignal,
): Promise<CohortAnalyticsResponse> {
  const query = new URLSearchParams({ program_id: params.programId });
  if (params.publicationId) query.set('publication_id', params.publicationId);
  if (params.termId) query.set('term_id', params.termId);
  if (params.courseId) query.set('course_id', params.courseId);
  const data: unknown = await request(`/api/v1/analytics/cohort/?${query}`, {
    signal,
    cache: 'no-store',
  });
  if (!isCohortAnalyticsResponse(data)) {
    throw new ApiError('unexpected', 200);
  }
  return data;
}

export async function getCohortTrends(
  params: CohortTrendsParams,
  signal?: AbortSignal,
): Promise<CohortTrendsResponse> {
  const query = new URLSearchParams({ program_id: params.programId });
  if (params.poSetVersion !== undefined) {
    query.set('po_set_version', String(params.poSetVersion));
  }
  if (params.publicationIds && params.publicationIds.length > 0) {
    query.set('publication_ids', params.publicationIds.join(','));
  }
  const data: unknown = await request(`/api/v1/analytics/trends/?${query}`, {
    signal,
    cache: 'no-store',
  });
  if (!isCohortTrendsResponse(data)) {
    throw new ApiError('unexpected', 200);
  }
  return data;
}

export async function getCoordinatorPrograms(
  signal?: AbortSignal,
): Promise<CohortProgramOption[]> {
  const data: unknown = await request('/api/v1/programs/?page_size=200', {
    signal,
    cache: 'no-store',
  });
  const items = extractResultsArray(data);
  if (!items) throw new ApiError('unexpected', 200);
  const programs: CohortProgramOption[] = [];
  for (const row of items) {
    if (
      !isRecord(row) ||
      typeof row.id !== 'string' ||
      typeof row.title !== 'string'
    ) {
      throw new ApiError('unexpected', 200);
    }
    const code = typeof row.code === 'string' && row.code ? `${row.code} · ` : '';
    programs.push({
      id: row.id,
      label: `${code}${row.title}`,
    });
  }
  return programs;
}

export async function getCohortTerms(
  signal?: AbortSignal,
): Promise<CohortTermOption[]> {
  const data: unknown = await request('/api/v1/terms/?page_size=200', {
    signal,
    cache: 'no-store',
  });
  const items = extractResultsArray(data);
  if (!items) throw new ApiError('unexpected', 200);
  const terms: CohortTermOption[] = [];
  for (const row of items) {
    if (
      !isRecord(row) ||
      typeof row.id !== 'string' ||
      typeof row.year !== 'number' ||
      typeof row.season !== 'string'
    ) {
      throw new ApiError('unexpected', 200);
    }
    const season =
      row.season.charAt(0).toUpperCase() + row.season.slice(1).toLowerCase();
    terms.push({
      id: row.id,
      label: `${row.year} ${season}`,
    });
  }
  return terms;
}

export async function getCohortCourses(
  signal?: AbortSignal,
): Promise<CohortCourseOption[]> {
  const data: unknown = await request('/api/v1/courses/?page_size=200', {
    signal,
    cache: 'no-store',
  });
  const items = extractResultsArray(data);
  if (!items) throw new ApiError('unexpected', 200);
  const courses: CohortCourseOption[] = [];
  for (const row of items) {
    if (
      !isRecord(row) ||
      typeof row.id !== 'string' ||
      typeof row.code !== 'string' ||
      typeof row.title !== 'string'
    ) {
      throw new ApiError('unexpected', 200);
    }
    courses.push({
      id: row.id,
      label: `${row.code} · ${row.title}`,
    });
  }
  return courses;
}

export function formatCoveragePercent(coverage: string): string {
  const ratio = Number(coverage);
  if (!Number.isFinite(ratio) || ratio < 0) return '0%';
  const pct = Math.round(ratio * 1000) / 10;
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`;
}

export function shortRef(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function isIncompatiblePoSetError(details: unknown): boolean {
  if (!details) return false;
  const serialized =
    typeof details === 'string' ? details : JSON.stringify(details);
  return /incompatible_po_set_version|different PO-set versions|different programs/i.test(
    serialized,
  );
}

export function cohortErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Unable to load cohort analytics. Please try again.';
  }
  if (error.kind === 'unauthorized') {
    return 'Your session has expired. Sign in again to view cohort analytics.';
  }
  if (error.kind === 'forbidden') {
    return 'You do not have permission to view cohort analytics for this scope.';
  }
  if (error.status === 404) {
    return 'No published cohort analytics available for the selected scope.';
  }
  if (error.kind === 'validation') {
    if (isIncompatiblePoSetError(error.details)) {
      return 'Cannot compare trends across incompatible PO-set versions. Changed PO definitions are not a performance trend.';
    }
    return 'The selected analytics filters are invalid. Check your selection and try again.';
  }
  if (error.kind === 'unavailable') {
    return 'Cohort analytics could not be loaded right now. Please try again.';
  }
  return 'Unable to load cohort analytics. Please try again.';
}
