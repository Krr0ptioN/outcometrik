export type PublicationAudience = 'student' | 'faculty';
export type PublicationScopeKind = 'program' | 'offering';

export type OutcomeScoreLevel = 'lo' | 'course_po' | 'cumulative_po';
export type OutcomeScoreStatus =
  | 'OK'
  | 'INCOMPLETE'
  | 'UNMAPPED'
  | 'NOT_ASSESSED'
  | 'ALL_EXEMPT';

export interface ProgramOutcomeMetadata {
  code: string;
  label: string;
  description: string;
  ordering: number;
}

export interface StudentPublication {
  id: string;
  program: string;
  program_code: string | null;
  program_title: string | null;
  offering: string | null;
  offering_label: string | null;
  term: string | null;
  term_label: string | null;
  run: string;
  scope_kind: PublicationScopeKind;
  series_version: number;
  po_set_version: number;
  audience: PublicationAudience;
  published_at: string;
  stale: boolean;
  program_outcomes: ProgramOutcomeMetadata[];
}

export interface AssessmentEvidenceContribution {
  assessment_code: string;
  weight: string;
  points_earned: string | null;
  points_possible: string | null;
  normalized_score: string | null;
  grade_state: string;
  grade_version: number | null;
  batch_released_at: string | null;
}

export interface LoEvidenceContribution {
  lo_code: string;
  learning_outcome_id: string | null;
  weight: string;
  value: string | null;
  lo_status: string | null;
  numerator: string | null;
  denominator: string | null;
  assessment_contributions: AssessmentEvidenceContribution[];
  missing: string[];
  exemptions: Array<{ label: string; reason: string }>;
}

export interface CourseEvidenceContribution {
  course_code: string;
  offering_id: string;
  term: string;
  syllabus_id: string | null;
  syllabus_version: number | null;
  attempt_number: number | null;
  weight: string;
  course_po_status: string;
  course_po_value: string | null;
  value: string | null;
  lo_contributions: LoEvidenceContribution[];
}

export interface OutcomeScoreEvidence {
  kernel_version?: string;
  policy_version?: string;
  display_value?: string | null;
  exact_value?: string | null;
  syllabus_id?: string | null;
  syllabus_version?: number | null;
  contributions?: Array<Record<string, unknown>>;
  missing?: string[];
  exemptions?: Array<Record<string, unknown>>;
}

export interface StudentOutcomeScore {
  id: string;
  run: string;
  level: OutcomeScoreLevel;
  student: number | string;
  offering: string | null;
  learning_outcome: string | null;
  program_outcome: string | null;
  outcome_code: string;
  value: string | null;
  display_value: string | null;
  numerator: string | null;
  denominator: string | null;
  coverage: string;
  status: OutcomeScoreStatus;
  evidence: OutcomeScoreEvidence;
}

export interface StudentPOProfileItem {
  code: string;
  label: string;
  description: string;
  status: OutcomeScoreStatus;
  statusLabel: string;
  /** Numeric 0..100 score when measured (including real 0.0); strictly null when unassessed/incomplete/unmapped/all-exempt. */
  value: number | null;
  /** Rounded 1-decimal string (e.g. "85.0", "0.0") or "—" when value is null. */
  displayValue: string;
  coveragePercent: number | null;
  coverageDisplay: string;
  numerator: string | null;
  denominator: string | null;
  formula: string;
  level: OutcomeScoreLevel | null;
  courses: CourseEvidenceContribution[];
  learningOutcomes: LoEvidenceContribution[];
  missing: string[];
  exemptions: Array<{ label: string; reason: string }>;
  sourceRevisions: string[];
}
