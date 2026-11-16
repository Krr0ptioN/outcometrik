import { ApiError, request } from '@outcometrik/api';

export interface Outcome {
  id: string;
  code: string;
  description: string;
  order: number;
}
export interface Assessment {
  id: string;
  code: string;
  kind: string;
  order: number;
  is_required: boolean;
  is_active: boolean;
  max_points: string;
}
export interface Syllabus {
  id: string;
  offering: string;
  version: number;
  status: 'draft' | 'approved' | 'retired';
  approved_at: string | null;
  po_set_version: number | null;
  learning_outcomes: Outcome[];
  assessments: Assessment[];
}
const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);
function isOutcome(v: unknown): v is Outcome {
  return (
    record(v) &&
    typeof v.id === 'string' &&
    typeof v.code === 'string' &&
    typeof v.description === 'string' &&
    typeof v.order === 'number'
  );
}
function isAssessment(v: unknown): v is Assessment {
  return (
    record(v) &&
    typeof v.id === 'string' &&
    typeof v.code === 'string' &&
    typeof v.kind === 'string' &&
    typeof v.order === 'number' &&
    typeof v.is_required === 'boolean' &&
    typeof v.is_active === 'boolean' &&
    typeof v.max_points === 'string'
  );
}
function isSyllabus(v: unknown): v is Syllabus {
  return (
    record(v) &&
    typeof v.id === 'string' &&
    typeof v.offering === 'string' &&
    typeof v.version === 'number' &&
    ['draft', 'approved', 'retired'].includes(String(v.status)) &&
    (v.approved_at === null || typeof v.approved_at === 'string') &&
    (v.po_set_version === null || typeof v.po_set_version === 'number') &&
    Array.isArray(v.learning_outcomes) &&
    v.learning_outcomes.every(isOutcome) &&
    Array.isArray(v.assessments) &&
    v.assessments.every(isAssessment)
  );
}
export async function getSyllabi(
  offering: string,
  signal?: AbortSignal,
): Promise<Syllabus[]> {
  const results: Syllabus[] = [];
  let page = 1;
  for (;;) {
    const data: unknown = await request(
      `/api/v1/syllabi/?offering=${encodeURIComponent(offering)}&page=${page}`,
      { signal, cache: 'no-store' },
    );
    if (
      !record(data) ||
      !Array.isArray(data.results) ||
      !data.results.every(isSyllabus) ||
      !(data.next === null || typeof data.next === 'string')
    )
      throw new ApiError('unexpected', 200);
    results.push(...data.results);
    if (data.next === null) return results;
    page += 1;
  }
}
export async function changeSyllabus(
  path: string,
  body?: unknown,
  method = 'POST',
) {
  await request(`/api/v1/syllabi/${path}`, { method, body });
}

export interface ProgramOutcomeSet {
  id: string;
  version: number;
  active: boolean;
  activated_at: string | null;
  effective_date: string;
  source_reference: string;
}
export async function getProgramOutcomeSets(
  program: string,
  signal?: AbortSignal,
): Promise<ProgramOutcomeSet[]> {
  const results: ProgramOutcomeSet[] = [];
  let page = 1;
  for (;;) {
    const data: unknown = await request(
      `/api/v1/po-sets/?program=${encodeURIComponent(program)}&page=${page}`,
      { signal, cache: 'no-store' },
    );
    if (
      !record(data) ||
      !Array.isArray(data.results) ||
      !(data.next === null || typeof data.next === 'string')
    )
      throw new ApiError('unexpected', 200);
    for (const item of data.results) {
      if (
        !record(item) ||
        typeof item.id !== 'string' ||
        typeof item.version !== 'number' ||
        typeof item.active !== 'boolean' ||
        !(
          item.activated_at === null || typeof item.activated_at === 'string'
        ) ||
        typeof item.effective_date !== 'string' ||
        typeof item.source_reference !== 'string'
      )
        throw new ApiError('unexpected', 200);
      results.push({
        id: item.id,
        version: item.version,
        active: item.active,
        activated_at: item.activated_at,
        effective_date: item.effective_date,
        source_reference: item.source_reference,
      });
    }
    if (data.next === null) return results;
    page += 1;
  }
}
export async function changeProgramOutcomeSet(
  path: string,
  body?: object,
  method = 'POST',
) {
  await request(`/api/v1/po-sets/${path}`, { method, body });
}

export interface ProgramOutcome {
  id: string;
  code: string;
  label: string;
  description: string;
  source_reference: string;
  order: number;
}
export async function getProgramOutcomes(
  id: string,
  signal?: AbortSignal,
): Promise<ProgramOutcome[]> {
  const data: unknown = await request(`/api/v1/po-sets/${id}/outcomes/`, {
    signal,
    cache: 'no-store',
  });
  if (
    !Array.isArray(data) ||
    !data.every(
      (item) =>
        record(item) &&
        typeof item.id === 'string' &&
        typeof item.code === 'string' &&
        typeof item.label === 'string' &&
        typeof item.description === 'string' &&
        typeof item.source_reference === 'string' &&
        typeof item.order === 'number',
    )
  )
    throw new ApiError('unexpected', 200);
  return data as ProgramOutcome[];
}
