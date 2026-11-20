import { ApiError } from '@outcometrik/api';
import type {
  AssessmentEvidenceContribution,
  CourseEvidenceContribution,
  LoEvidenceContribution,
  OutcomeScoreStatus,
  ProgramOutcomeMetadata,
  StudentOutcomeScore,
  StudentPOProfileItem,
} from './types';

export const CANONICAL_PO_CODES = [
  'PO1',
  'PO2',
  'PO3',
  'PO4',
  'PO5',
  'PO6',
  'PO7',
  'PO8',
  'PO9',
  'PO10',
  'PO11',
] as const;

const STATUS_LABELS: Record<OutcomeScoreStatus, string> = {
  OK: 'Measured',
  NOT_ASSESSED: 'Not assessed',
  INCOMPLETE: 'Incomplete',
  UNMAPPED: 'Unmapped',
  ALL_EXEMPT: 'All exempt',
};

const WEIGHTED_AVERAGE_FORMULA = 'Σ (weight × source_score) / Σ (weight)';

/**
 * Normalizes PO codes such as "PO-1", "po 01", or "PO1" into canonical key "PO1".
 */
export function normalizePoCode(code: string): string {
  const match = /^po[\s_-]*0*(\d+)$/i.exec(code.trim());
  if (!match) return code.trim().toUpperCase();
  return `PO${Number.parseInt(match[1], 10)}`;
}

/**
 * Exact decimal string rounding to 1 decimal place using ROUND_HALF_UP (no float drift).
 */
export function roundHalfUpOneDecimal(raw: string | number): string {
  const input = typeof raw === 'number' ? String(raw) : raw.trim();
  const match = /^([+-])?(\d+)(?:\.(\d+))?$/.exec(input);
  if (!match) {
    const parsed = Number(input);
    if (!Number.isFinite(parsed)) return '0.0';
    return parsed.toFixed(1);
  }
  const sign = match[1] === '-' ? '-' : '';
  const intPart = match[2];
  const fracPart = match[3] ?? '';
  const padded = `${fracPart}00`;
  const tenths = Number.parseInt(padded[0], 10);
  const hundredths = Number.parseInt(padded[1], 10);

  let scaled = BigInt(intPart) * 10n + BigInt(tenths);
  if (hundredths >= 5) {
    scaled += 1n;
  }

  const whole = scaled / 10n;
  const decimal = scaled % 10n;
  const result = `${whole}.${decimal}`;
  return scaled === 0n ? '0.0' : `${sign}${result}`;
}

function asText(value: unknown): string | null {
  if (typeof value === 'string' && value.length > 0) return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseAssessmentContribution(
  raw: Record<string, unknown>,
): AssessmentEvidenceContribution {
  return {
    assessment_code: asText(raw.assessment_code) ?? 'Assessment',
    weight: asText(raw.weight) ?? '—',
    points_earned: asText(raw.points_earned),
    points_possible: asText(raw.points_possible),
    normalized_score: asText(raw.normalized_score),
    grade_state: asText(raw.grade_state) ?? 'unknown',
    grade_version:
      typeof raw.grade_version === 'number' ? raw.grade_version : null,
    batch_released_at: asText(raw.batch_released_at),
  };
}

function parseExemptions(
  raw: unknown,
): Array<{ label: string; reason: string }> {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    const rec = asRecord(item);
    if (!rec) return [];
    const label =
      asText(rec.assessment_code) ??
      asText(rec.lo_code) ??
      asText(rec.course_code) ??
      'Item';
    const reason = asText(rec.reason) ?? 'Exempt';
    return [{ label, reason }];
  });
}

function parseLoContribution(
  raw: Record<string, unknown>,
  loRowsById: Map<string, StudentOutcomeScore>,
): LoEvidenceContribution {
  const loId = asText(raw.learning_outcome_id);
  const linkedLoRow = loId ? loRowsById.get(loId) : undefined;

  const rawAssessments = Array.isArray(raw.assessment_contributions)
    ? raw.assessment_contributions
    : (linkedLoRow?.evidence.contributions ?? []);

  const assessmentContributions = rawAssessments
    .map(asRecord)
    .filter((entry): entry is Record<string, unknown> => entry !== null)
    .map(parseAssessmentContribution);

  const rawMissing = Array.isArray(raw.missing)
    ? raw.missing.filter((m): m is string => typeof m === 'string')
    : (linkedLoRow?.evidence.missing ?? []);

  const rawExemptions =
    raw.exemptions !== undefined
      ? parseExemptions(raw.exemptions)
      : parseExemptions(linkedLoRow?.evidence.exemptions);

  return {
    lo_code: asText(raw.lo_code) ?? linkedLoRow?.outcome_code ?? 'LO',
    learning_outcome_id: loId,
    weight: asText(raw.weight) ?? '—',
    value: asText(raw.value) ?? asText(raw.lo_value) ?? linkedLoRow?.value ?? null,
    lo_status: asText(raw.lo_status) ?? linkedLoRow?.status ?? null,
    numerator: asText(raw.numerator) ?? linkedLoRow?.numerator ?? null,
    denominator: asText(raw.denominator) ?? linkedLoRow?.denominator ?? null,
    assessment_contributions: assessmentContributions,
    missing: rawMissing,
    exemptions: rawExemptions,
  };
}

function parseCourseContribution(
  raw: Record<string, unknown>,
  loRowsById: Map<string, StudentOutcomeScore>,
): CourseEvidenceContribution {
  const rawLos = Array.isArray(raw.lo_contributions)
    ? raw.lo_contributions
    : [];
  const loContributions = rawLos
    .map(asRecord)
    .filter((entry): entry is Record<string, unknown> => entry !== null)
    .map((entry) => parseLoContribution(entry, loRowsById));

  return {
    course_code: asText(raw.course_code) ?? 'Course',
    offering_id: asText(raw.offering_id) ?? '',
    term: asText(raw.term) ?? '',
    syllabus_id: asText(raw.syllabus_id),
    syllabus_version:
      typeof raw.syllabus_version === 'number' ? raw.syllabus_version : null,
    attempt_number:
      typeof raw.attempt_number === 'number' ? raw.attempt_number : null,
    weight: asText(raw.weight) ?? '—',
    course_po_status: asText(raw.course_po_status) ?? 'OK',
    course_po_value: asText(raw.course_po_value),
    value: asText(raw.value),
    lo_contributions: loContributions,
  };
}

function formatCoverage(
  rawCoverage: string | null,
  status: OutcomeScoreStatus,
): { percent: number | null; display: string } {
  if (status === 'NOT_ASSESSED' || status === 'UNMAPPED' || rawCoverage === null) {
    return { percent: null, display: '—' };
  }
  const numeric = Number(rawCoverage);
  if (!Number.isFinite(numeric)) {
    return { percent: null, display: '—' };
  }
  const pct = Math.max(0, Math.min(100, Math.round(numeric * 1000) / 10));
  const formatted = Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`;
  return { percent: pct, display: formatted };
}

function buildSourceRevisions(score: StudentOutcomeScore): string[] {
  const revisions: string[] = [];
  if (score.evidence.kernel_version) {
    revisions.push(`Kernel ${score.evidence.kernel_version}`);
  }
  if (score.evidence.policy_version) {
    revisions.push(`Policy ${score.evidence.policy_version}`);
  }
  if (score.evidence.syllabus_version != null) {
    revisions.push(`Syllabus v${score.evidence.syllabus_version}`);
  }
  return revisions;
}

/**
 * Pure helper that builds an ordered PO1–PO11 student profile from frozen OutcomeScore rows.
 * Guarantees all 11 canonical PO codes are always present; unassessed/incomplete/unmapped/exempt
 * POs always carry `value: null` and explicit text status (never numeric 0), while a real measured
 * zero displays "0.0" with status "Measured".
 */
export function buildStudentPOProfile(
  scores: readonly StudentOutcomeScore[],
  expectedOutcomes?: readonly (string | ProgramOutcomeMetadata)[],
): StudentPOProfileItem[] {
  const metadataByKey = new Map<string, ProgramOutcomeMetadata>();
  const orderedKeys: string[] = [];

  if (expectedOutcomes && expectedOutcomes.length > 0) {
    for (let idx = 0; idx < expectedOutcomes.length; idx += 1) {
      const entry = expectedOutcomes[idx];
      const meta: ProgramOutcomeMetadata =
        typeof entry === 'string'
          ? { code: entry, label: '', description: '', ordering: idx + 1 }
          : entry;
      const key = normalizePoCode(meta.code);
      if (!metadataByKey.has(key)) {
        metadataByKey.set(key, meta);
        orderedKeys.push(key);
      }
    }
  }

  for (let idx = 0; idx < CANONICAL_PO_CODES.length; idx += 1) {
    const canonical = CANONICAL_PO_CODES[idx];
    if (!metadataByKey.has(canonical)) {
      metadataByKey.set(canonical, {
        code: canonical,
        label: '',
        description: '',
        ordering: idx + 1,
      });
      orderedKeys.push(canonical);
    }
  }

  const hasCumulative = scores.some((row) => row.level === 'cumulative_po');
  const targetLevel = hasCumulative ? 'cumulative_po' : 'course_po';

  const poScoreByKey = new Map<string, StudentOutcomeScore>();
  const loRowsById = new Map<string, StudentOutcomeScore>();

  for (const row of scores) {
    if (row.level === 'lo' && row.learning_outcome) {
      loRowsById.set(row.learning_outcome, row);
    }
    if (row.level === targetLevel) {
      const key = normalizePoCode(row.outcome_code);
      poScoreByKey.set(key, row);
      if (!metadataByKey.has(key)) {
        metadataByKey.set(key, {
          code: row.outcome_code,
          label: '',
          description: '',
          ordering: orderedKeys.length + 1,
        });
        orderedKeys.push(key);
      }
    }
  }

  return orderedKeys.map((key) => {
    const meta = metadataByKey.get(key)!;
    const score = poScoreByKey.get(key);

    if (!score) {
      return {
        code: key,
        label: meta.label,
        description: meta.description,
        status: 'NOT_ASSESSED',
        statusLabel: STATUS_LABELS.NOT_ASSESSED,
        value: null,
        displayValue: '—',
        coveragePercent: null,
        coverageDisplay: '—',
        numerator: null,
        denominator: null,
        formula: WEIGHTED_AVERAGE_FORMULA,
        level: null,
        courses: [],
        learningOutcomes: [],
        missing: [],
        exemptions: [],
        sourceRevisions: [],
      };
    }

    const isMeasured = score.status === 'OK' && score.value !== null;
    const displayValue = isMeasured
      ? score.display_value && score.display_value.trim().length > 0
        ? score.display_value.trim()
        : roundHalfUpOneDecimal(score.value as string)
      : '—';
    const numericValue = isMeasured ? Number(displayValue) : null;
    const coverage = formatCoverage(score.coverage, score.status);

    const rawContributions = score.evidence.contributions ?? [];
    const courses: CourseEvidenceContribution[] =
      score.level === 'cumulative_po'
        ? rawContributions.map((entry) =>
            parseCourseContribution(entry, loRowsById),
          )
        : [];
    const learningOutcomes: LoEvidenceContribution[] =
      score.level === 'course_po'
        ? rawContributions.map((entry) =>
            parseLoContribution(entry, loRowsById),
          )
        : [];

    return {
      code: key,
      label: meta.label,
      description: meta.description,
      status: score.status,
      statusLabel: STATUS_LABELS[score.status],
      value: numericValue,
      displayValue,
      coveragePercent: coverage.percent,
      coverageDisplay: coverage.display,
      numerator: score.numerator,
      denominator: score.denominator,
      formula: WEIGHTED_AVERAGE_FORMULA,
      level: score.level,
      courses,
      learningOutcomes,
      missing: score.evidence.missing ?? [],
      exemptions: parseExemptions(score.evidence.exemptions),
      sourceRevisions: buildSourceRevisions(score),
    };
  });
}

export function studentProfileErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'unauthorized') {
      return 'Your session expired. Sign in again to view your published outcomes.';
    }
    if (error.kind === 'forbidden' || error.status === 404) {
      return 'This published outcome snapshot is not available for your account.';
    }
    if (error.kind === 'unavailable') {
      return 'Unable to reach the server. Try again in a moment.';
    }
  }
  return 'Unable to load your published outcome profile right now.';
}
