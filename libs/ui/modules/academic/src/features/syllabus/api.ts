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

export interface CoursePOContribution {
  id: string;
  syllabus?: string;
  program_outcome: string;
  program_outcome_code: string;
  weight: number;
  governance_role?: string;
  governance_level?: string;

export interface AssessmentLOMapping {
  id?: string;
  syllabus?: string;
  assessment: string;
  learning_outcome: string;
  weight: string;
  is_active: boolean;
}
export interface LOPOMapping {
  id?: string;
  syllabus?: string;
  learning_outcome: string;
  program_outcome: string;
  weight: number;
  is_active: boolean;
}
export interface LearningOutcomeMappingStatus {
  learning_outcome_id: string;
  code: string;
  status: 'MAPPED' | 'UNMAPPED';
  total_assessment_weight: string;
  mapped_po_count: number;
}
export interface ProgramOutcomeMappingStatus {
  program_outcome_id: string;
  code: string;
  status: 'ASSESSED' | 'NOT_ASSESSED';
  total_lo_weight: number;
}
export interface SyllabusMappingValidation {
  syllabus_id: string;
  mapping_revision: number;
  is_valid_for_approval: boolean;
  lo_statuses: LearningOutcomeMappingStatus[];
  po_statuses: ProgramOutcomeMappingStatus[];
  unmapped_learning_outcomes: string[];
  orphaned_learning_outcomes: string[];
  unreachable_program_outcomes: string[];
  errors: string[];

}
export interface Syllabus {
  id: string;
  offering: string;
  version: number;
  status: 'draft' | 'approved' | 'retired';
  approved_at: string | null;
  po_set_version: number | null;
  mapping_revision?: number;
  learning_outcomes: Outcome[];
  assessments: Assessment[];

  po_contributions?: CoursePOContribution[];

  assessment_lo_mappings?: AssessmentLOMapping[];
  lo_po_mappings?: LOPOMapping[];

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

export function isCoursePOContribution(v: unknown): v is CoursePOContribution {
  return (
    record(v) &&
    typeof v.id === 'string' &&
    typeof v.program_outcome === 'string' &&
    typeof v.program_outcome_code === 'string' &&
    typeof v.weight === 'number' &&
    Number.isInteger(v.weight) &&
    v.weight >= 1 &&
    v.weight <= 5
  );
}

function isAssessmentLOMapping(v: unknown): v is AssessmentLOMapping {
  return (
    record(v) &&
    typeof v.assessment === 'string' &&
    typeof v.learning_outcome === 'string' &&
    typeof v.weight === 'string' &&
    typeof v.is_active === 'boolean'
  );
}
function isLOPOMapping(v: unknown): v is LOPOMapping {
  return (
    record(v) &&
    typeof v.learning_outcome === 'string' &&
    typeof v.program_outcome === 'string' &&
    typeof v.weight === 'number' &&
    typeof v.is_active === 'boolean'
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
    (v.mapping_revision === undefined ||
      typeof v.mapping_revision === 'number') &&
    Array.isArray(v.learning_outcomes) &&
    v.learning_outcomes.every(isOutcome) &&
    Array.isArray(v.assessments) &&
    v.assessments.every(isAssessment) &&
    (v.po_contributions === undefined ||
      (Array.isArray(v.po_contributions) &&
        v.po_contributions.every(isCoursePOContribution))) &&
    (v.assessment_lo_mappings === undefined ||
      (Array.isArray(v.assessment_lo_mappings) &&
        v.assessment_lo_mappings.every(isAssessmentLOMapping))) &&
    (v.lo_po_mappings === undefined ||
      (Array.isArray(v.lo_po_mappings) &&
        v.lo_po_mappings.every(isLOPOMapping)))
  );
}
function isLearningOutcomeMappingStatus(
  v: unknown,
): v is LearningOutcomeMappingStatus {
  return (
    record(v) &&
    typeof v.learning_outcome_id === 'string' &&
    typeof v.code === 'string' &&
    (v.status === 'MAPPED' || v.status === 'UNMAPPED') &&
    typeof v.total_assessment_weight === 'string' &&
    typeof v.mapped_po_count === 'number'
  );
}
function isProgramOutcomeMappingStatus(
  v: unknown,
): v is ProgramOutcomeMappingStatus {
  return (
    record(v) &&
    typeof v.program_outcome_id === 'string' &&
    typeof v.code === 'string' &&
    (v.status === 'ASSESSED' || v.status === 'NOT_ASSESSED') &&
    typeof v.total_lo_weight === 'number'
  );
}
function isSyllabusMappingValidation(
  v: unknown,
): v is SyllabusMappingValidation {
  return (
    record(v) &&
    typeof v.syllabus_id === 'string' &&
    typeof v.mapping_revision === 'number' &&
    typeof v.is_valid_for_approval === 'boolean' &&
    Array.isArray(v.lo_statuses) &&
    v.lo_statuses.every(isLearningOutcomeMappingStatus) &&
    Array.isArray(v.po_statuses) &&
    v.po_statuses.every(isProgramOutcomeMappingStatus) &&
    Array.isArray(v.unmapped_learning_outcomes) &&
    v.unmapped_learning_outcomes.every((x) => typeof x === 'string') &&
    Array.isArray(v.orphaned_learning_outcomes) &&
    v.orphaned_learning_outcomes.every((x) => typeof x === 'string') &&
    Array.isArray(v.unreachable_program_outcomes) &&
    v.unreachable_program_outcomes.every((x) => typeof x === 'string') &&
    Array.isArray(v.errors) &&
    v.errors.every((x) => typeof x === 'string')
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
export async function replaceAssessmentLOMappings(
  syllabusId: string,
  expectedRevision: number,
  mappings: Array<{
    assessment: string;
    learning_outcome: string;
    weight: string;
    is_active?: boolean;
  }>,
): Promise<Syllabus> {
  const data: unknown = await request(
    `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/assessment-lo-mappings/`,
    {
      method: 'POST',
      body: {
        expected_revision: expectedRevision,
        mappings,
      },
    },
  );
  if (!isSyllabus(data)) throw new ApiError('unexpected', 200);
  return data;
}
export async function replaceLOPOMappings(
  syllabusId: string,
  expectedRevision: number,
  mappings: Array<{
    learning_outcome: string;
    program_outcome: string;
    weight: number;
    is_active?: boolean;
  }>,
): Promise<Syllabus> {
  const data: unknown = await request(
    `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/lo-po-mappings/`,
    {
      method: 'POST',
      body: {
        expected_revision: expectedRevision,
        mappings,
      },
    },
  );
  if (!isSyllabus(data)) throw new ApiError('unexpected', 200);
  return data;
}
export async function getSyllabusMappingValidation(
  syllabusId: string,
  signal?: AbortSignal,
): Promise<SyllabusMappingValidation> {
  const data: unknown = await request(
    `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/mapping-validation/`,
    {
      signal,
      cache: 'no-store',
    },
  );
  if (!isSyllabusMappingValidation(data)) throw new ApiError('unexpected', 200);
  return data;
}

export async function getSyllabusPOContributions(
  syllabusId: string,
  signal?: AbortSignal,
): Promise<CoursePOContribution[]> {
  const data: unknown = await request(
    `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/po-contributions/`,
    { signal, cache: 'no-store' },
  );
  if (!Array.isArray(data) || !data.every(isCoursePOContribution))
    throw new ApiError('unexpected', 200);
  return data;
}

export async function saveSyllabusPOContribution(
  syllabusId: string,
  payload: { program_outcome: string; weight: number },
  contributionId?: string,
): Promise<CoursePOContribution> {
  const path: `/api/${string}` = contributionId
    ? `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/po-contributions/${encodeURIComponent(contributionId)}/`
    : `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/po-contributions/`;
  const data: unknown = await request(path, {
    method: contributionId ? 'PATCH' : 'POST',
    body: payload,
  });
  if (!isCoursePOContribution(data)) throw new ApiError('unexpected', 200);
  return data;
}

export async function deleteSyllabusPOContribution(
  syllabusId: string,
  contributionId: string,
): Promise<void> {
  await request(
    `/api/v1/syllabi/${encodeURIComponent(syllabusId)}/po-contributions/${encodeURIComponent(contributionId)}/`,
    { method: 'DELETE' },
  );
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
