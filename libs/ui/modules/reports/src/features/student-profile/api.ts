import { ApiError, request } from '@outcometrik/api';
import type {
  OutcomeScoreEvidence,
  OutcomeScoreLevel,
  OutcomeScoreStatus,
  ProgramOutcomeMetadata,
  PublicationAudience,
  PublicationScopeKind,
  StudentOutcomeScore,
  StudentPublication,
} from './types';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const VALID_LEVELS = new Set<OutcomeScoreLevel>([
  'lo',
  'course_po',
  'cumulative_po',
]);
const VALID_STATUSES = new Set<OutcomeScoreStatus>([
  'OK',
  'INCOMPLETE',
  'UNMAPPED',
  'NOT_ASSESSED',
  'ALL_EXEMPT',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function asNullableString(value: unknown): string | null | undefined {
  if (value === null) return null;
  if (typeof value === 'string') return value;
  return undefined;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asDecimalStringOrNull(value: unknown): string | null | undefined {
  if (value === null) return null;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return undefined;
}

function parseProgramOutcomes(value: unknown): ProgramOutcomeMetadata[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new ApiError('unexpected', 200);
  return value.map((item) => {
    if (!isRecord(item)) throw new ApiError('unexpected', 200);
    const code = asString(item.code);
    if (!code) throw new ApiError('unexpected', 200);
    return {
      code,
      label: typeof item.label === 'string' ? item.label : '',
      description: typeof item.description === 'string' ? item.description : '',
      ordering: typeof item.ordering === 'number' ? item.ordering : 0,
    };
  });
}

function parsePublication(raw: unknown): StudentPublication {
  if (!isRecord(raw)) throw new ApiError('unexpected', 200);
  const id = asString(raw.id);
  const program = asString(raw.program);
  const run = asString(raw.run);
  const publishedAt = asString(raw.published_at);
  const seriesVersion = asNumber(raw.series_version);
  const poSetVersion = asNumber(raw.po_set_version);
  const audience = raw.audience;
  const stale = raw.stale;
  const offering = asNullableString(raw.offering);
  const term = asNullableString(raw.term);

  if (
    !id ||
    !program ||
    !run ||
    !publishedAt ||
    seriesVersion === null ||
    poSetVersion === null ||
    (audience !== 'student' && audience !== 'faculty') ||
    typeof stale !== 'boolean' ||
    offering === undefined ||
    term === undefined
  ) {
    throw new ApiError('unexpected', 200);
  }

  const scopeKind: PublicationScopeKind =
    raw.scope_kind === 'offering' || raw.scope_kind === 'program'
      ? raw.scope_kind
      : offering
        ? 'offering'
        : 'program';

  return {
    id,
    program,
    program_code: typeof raw.program_code === 'string' ? raw.program_code : null,
    program_title:
      typeof raw.program_title === 'string' ? raw.program_title : null,
    offering,
    offering_label:
      typeof raw.offering_label === 'string' ? raw.offering_label : null,
    term,
    term_label: typeof raw.term_label === 'string' ? raw.term_label : null,
    run,
    scope_kind: scopeKind,
    series_version: seriesVersion,
    po_set_version: poSetVersion,
    audience: audience as PublicationAudience,
    published_at: publishedAt,
    stale,
    program_outcomes: parseProgramOutcomes(raw.program_outcomes),
  };
}

function parseEvidence(raw: unknown): OutcomeScoreEvidence {
  if (raw === null || raw === undefined) return {};
  if (!isRecord(raw)) throw new ApiError('unexpected', 200);
  const contributions =
    raw.contributions === undefined
      ? undefined
      : Array.isArray(raw.contributions) &&
          raw.contributions.every((entry) => isRecord(entry))
        ? raw.contributions
        : null;
  if (contributions === null) throw new ApiError('unexpected', 200);

  const missing =
    raw.missing === undefined
      ? undefined
      : Array.isArray(raw.missing) &&
          raw.missing.every((entry) => typeof entry === 'string')
        ? raw.missing
        : null;
  if (missing === null) throw new ApiError('unexpected', 200);

  const exemptions =
    raw.exemptions === undefined
      ? undefined
      : Array.isArray(raw.exemptions) &&
          raw.exemptions.every((entry) => isRecord(entry))
        ? raw.exemptions
        : null;
  if (exemptions === null) throw new ApiError('unexpected', 200);

  return {
    kernel_version:
      typeof raw.kernel_version === 'string' ? raw.kernel_version : undefined,
    policy_version:
      typeof raw.policy_version === 'string' ? raw.policy_version : undefined,
    display_value:
      raw.display_value === null || typeof raw.display_value === 'string'
        ? raw.display_value
        : undefined,
    exact_value:
      raw.exact_value === null || typeof raw.exact_value === 'string'
        ? raw.exact_value
        : undefined,
    syllabus_id:
      raw.syllabus_id === null || typeof raw.syllabus_id === 'string'
        ? raw.syllabus_id
        : undefined,
    syllabus_version:
      raw.syllabus_version === null || typeof raw.syllabus_version === 'number'
        ? raw.syllabus_version
        : undefined,
    contributions,
    missing,
    exemptions,
  };
}

function parseOutcomeScore(raw: unknown): StudentOutcomeScore {
  if (!isRecord(raw)) throw new ApiError('unexpected', 200);
  const id = asString(raw.id);
  const run = asString(raw.run);
  const outcomeCode = asString(raw.outcome_code);
  const level = raw.level;
  const status = raw.status;
  const student = raw.student;
  const value = asDecimalStringOrNull(raw.value);
  const displayValue =
    raw.display_value === undefined
      ? null
      : asDecimalStringOrNull(raw.display_value);
  const numerator = asDecimalStringOrNull(raw.numerator);
  const denominator = asDecimalStringOrNull(raw.denominator);
  const coverage = asDecimalStringOrNull(raw.coverage);

  if (
    !id ||
    !run ||
    !outcomeCode ||
    typeof level !== 'string' ||
    !VALID_LEVELS.has(level as OutcomeScoreLevel) ||
    typeof status !== 'string' ||
    !VALID_STATUSES.has(status as OutcomeScoreStatus) ||
    (typeof student !== 'number' && typeof student !== 'string') ||
    value === undefined ||
    displayValue === undefined ||
    numerator === undefined ||
    denominator === undefined ||
    coverage === undefined ||
    coverage === null
  ) {
    throw new ApiError('unexpected', 200);
  }

  return {
    id,
    run,
    level: level as OutcomeScoreLevel,
    student,
    offering: typeof raw.offering === 'string' ? raw.offering : null,
    learning_outcome:
      typeof raw.learning_outcome === 'string' ? raw.learning_outcome : null,
    program_outcome:
      typeof raw.program_outcome === 'string' ? raw.program_outcome : null,
    outcome_code: outcomeCode,
    value,
    display_value: displayValue,
    numerator,
    denominator,
    coverage,
    status: status as OutcomeScoreStatus,
    evidence: parseEvidence(raw.evidence),
  };
}

/**
 * Fetches immutable student-audience publications visible to the authenticated student.
 */
export async function getStudentPublications(
  signal?: AbortSignal,
): Promise<StudentPublication[]> {
  const payload = await request<unknown>('/api/v1/publications/', {
    method: 'GET',
    cache: 'no-store',
    signal,
  });

  let rows: unknown[];
  if (Array.isArray(payload)) {
    rows = payload;
  } else if (isRecord(payload) && Array.isArray(payload.results)) {
    rows = payload.results;
  } else {
    throw new ApiError('unexpected', 200);
  }

  return rows
    .map(parsePublication)
    .filter((pub) => pub.audience === 'student');
}

/**
 * Fetches the authenticated student's own immutable OutcomeScore rows for one publication.
 */
export async function getStudentPublicationScores(
  publicationId: string,
  signal?: AbortSignal,
): Promise<StudentOutcomeScore[]> {
  if (!UUID.test(publicationId)) {
    throw new ApiError('validation', 0, {
      publication_id: 'Choose a valid publication.',
    });
  }

  const payload = await request<unknown>(
    `/api/v1/publications/${encodeURIComponent(publicationId)}/scores/`,
    {
      method: 'GET',
      cache: 'no-store',
      signal,
    },
  );

  if (!Array.isArray(payload)) {
    throw new ApiError('unexpected', 200);
  }

  return payload.map(parseOutcomeScore);
}
