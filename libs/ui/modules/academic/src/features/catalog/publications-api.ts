import { ApiError, request } from '@outcometrik/api';

export interface CalculationRun {
  id: string;
  scope_kind: 'offering' | 'program' | string;
  program: string;
  offering: string | null;
  po_set_version: number;
  engine_version: string;
  policy_version: string;
  input_hash: string;
  manifest: Record<string, unknown>;
  status: string;
  is_complete_for_publication: boolean;
  error_detail: string;
  completed_at: string | null;
  created_at: string;
}

export type PublicationAudience = 'faculty' | 'student';

export interface GovernancePublication {
  id: string;
  program: string;
  program_code?: string;
  program_title?: string;
  offering: string | null;
  offering_label: string | null;
  term: string | null;
  term_label: string | null;
  run: string;
  scope_kind: string;
  series_version: number;
  po_set_version: number;
  audience: PublicationAudience | string;
  input_hash: string;
  idempotency_key: string;
  published_at: string | null;
  stale: boolean;
}

export interface PublishRunPayload {
  run: string;
  expected_series_version: number;
  expected_input_hash: string;
  audience: PublicationAudience;
  idempotency_key: string;
  term?: string | null;
}

export type PublicationFreshness = 'current' | 'stale' | 'historical';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isStringOrNull(value: unknown): value is string | null {
  return typeof value === 'string' || value === null;
}

function isCalculationRun(value: unknown): value is CalculationRun {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.scope_kind === 'string' &&
    typeof value.program === 'string' &&
    isStringOrNull(value.offering) &&
    typeof value.po_set_version === 'number' &&
    typeof value.engine_version === 'string' &&
    typeof value.policy_version === 'string' &&
    typeof value.input_hash === 'string' &&
    isRecord(value.manifest) &&
    typeof value.status === 'string' &&
    typeof value.is_complete_for_publication === 'boolean' &&
    typeof value.error_detail === 'string' &&
    isStringOrNull(value.completed_at) &&
    typeof value.created_at === 'string'
  );
}

function isGovernancePublication(value: unknown): value is GovernancePublication {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.program === 'string' &&
    isStringOrNull(value.offering) &&
    (value.offering_label === undefined ||
      isStringOrNull(value.offering_label)) &&
    isStringOrNull(value.term) &&
    (value.term_label === undefined || isStringOrNull(value.term_label)) &&
    typeof value.run === 'string' &&
    (value.scope_kind === undefined || typeof value.scope_kind === 'string') &&
    typeof value.series_version === 'number' &&
    typeof value.po_set_version === 'number' &&
    typeof value.audience === 'string' &&
    typeof value.input_hash === 'string' &&
    typeof value.idempotency_key === 'string' &&
    isStringOrNull(value.published_at) &&
    typeof value.stale === 'boolean'
  );
}

function extractResults(data: unknown): unknown[] | null {
  if (Array.isArray(data)) return data;
  if (isRecord(data) && Array.isArray(data.results)) return data.results;
  return null;
}

export async function getCalculationRuns(
  programId: string,
  signal?: AbortSignal,
): Promise<CalculationRun[]> {
  const query = new URLSearchParams({
    program: programId,
    page_size: '50',
  });
  const data: unknown = await request(`/api/v1/calculation-runs/?${query}`, {
    signal,
    cache: 'no-store',
  });
  const items = extractResults(data);
  if (!items || !items.every(isCalculationRun)) {
    throw new ApiError('unexpected', 200);
  }
  return items;
}

export async function runProgramCalculation(
  programId: string,
): Promise<CalculationRun> {
  const data: unknown = await request('/api/v1/calculation-runs/program/', {
    method: 'POST',
    body: { program: programId },
  });
  if (!isCalculationRun(data)) {
    throw new ApiError('unexpected', 201);
  }
  return data;
}

export async function getProgramPublications(
  programId: string,
  signal?: AbortSignal,
): Promise<GovernancePublication[]> {
  const query = new URLSearchParams({
    program: programId,
    page_size: '100',
  });
  const data: unknown = await request(`/api/v1/publications/?${query}`, {
    signal,
    cache: 'no-store',
  });
  const items = extractResults(data);
  if (!items || !items.every(isGovernancePublication)) {
    throw new ApiError('unexpected', 200);
  }
  return items;
}

export async function publishCalculationRun(
  payload: PublishRunPayload,
): Promise<GovernancePublication> {
  const data: unknown = await request('/api/v1/publications/', {
    method: 'POST',
    body: payload,
  });
  if (!isGovernancePublication(data)) {
    throw new ApiError('unexpected', 201);
  }
  return data;
}

/**
 * Resolves freshness state for a publication within its (scope_kind, offering, audience) series.
 * - If stale === true -> 'stale'
 * - Else if it is the highest series_version in its series -> 'current'
 * - Else -> 'historical'
 */
export function resolvePublicationFreshness(
  pub: GovernancePublication,
  allPublications: GovernancePublication[],
): PublicationFreshness {
  const sameSeries = allPublications.filter(
    (other) =>
      other.program === pub.program &&
      other.offering === pub.offering &&
      other.audience === pub.audience,
  );
  const maxVersion = sameSeries.reduce(
    (max, item) => Math.max(max, item.series_version),
    pub.series_version,
  );
  if (pub.series_version < maxVersion) {
    return 'historical';
  }
  return pub.stale ? 'stale' : 'current';
}

export function buildPublishIdempotencyKey(params: {
  programId: string;
  runId: string;
  expectedSeriesVersion: number;
  audience: PublicationAudience;
}): string {
  const prog = params.programId.slice(0, 8);
  const run = params.runId.slice(0, 8);
  return `pub-${prog}-${run}-v${params.expectedSeriesVersion + 1}-${params.audience}`;
}

export interface PublicationConflictInfo {
  isConflict: boolean;
  code: string | null;
  message: string;
}

export function parsePublicationConflict(
  error: unknown,
): PublicationConflictInfo {
  if (!(error instanceof ApiError)) {
    return {
      isConflict: false,
      code: null,
      message: 'Unable to publish calculation run. Please try again.',
    };
  }
  if (error.status === 409 || error.kind === 'conflict') {
    const details = isRecord(error.details) ? error.details : null;
    const code = typeof details?.code === 'string' ? details.code : 'conflict';
    const detail =
      typeof details?.detail === 'string'
        ? details.detail
        : 'Underlying grades, syllabus mappings, or series version changed since this calculation run was computed. Re-run calculation and try publishing again.';
    return {
      isConflict: true,
      code,
      message: detail,
    };
  }
  if (error.kind === 'forbidden') {
    return {
      isConflict: false,
      code: 'forbidden',
      message: 'You do not have permission to publish outcomes for this program.',
    };
  }
  return {
    isConflict: false,
    code: null,
    message: 'Unable to publish calculation run. Please verify readiness gates and try again.',
  };
}
