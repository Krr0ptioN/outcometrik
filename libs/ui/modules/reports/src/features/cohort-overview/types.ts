export type PublicationStatus = 'published' | 'stale';

export interface CoordinatorPublication {
  id: string;
  program: string;
  offering: string | null;
  term: string | null;
  run: string;
  series_version: number;
  po_set_version: number;
  audience: string;
  published_at: string | null;
  stale: boolean;
}

export interface CohortExclusions {
  NOT_ASSESSED: number;
  INCOMPLETE: number;
  ALL_EXEMPT: number;
  UNMAPPED: number;
}

export interface CohortDistribution {
  '<50': number;
  '50-69.9': number;
  '70-84.9': number;
  '85-100': number;
}

export interface CohortOutcomeMetric {
  program_outcome_id: string | null;
  code: string;
  label: string;
  n: number;
  population_size: number;
  coverage: string;
  mean: string | null;
  median: string | null;
  min: string | null;
  max: string | null;
  distribution: CohortDistribution;
  exclusions: CohortExclusions;
}

export interface CohortAnalyticsFilters {
  course_id: string | null;
  term_id: string | null;
}

export interface CohortAnalyticsResponse {
  publication_id: string;
  run_id: string;
  series_version: number;
  program_id: string;
  offering_id: string | null;
  term_id: string | null;
  po_set_version: number;
  policy_version: string;
  engine_version: string;
  publication_status: PublicationStatus;
  audience: string;
  published_at: string | null;
  filters: CohortAnalyticsFilters;
  sample_size: number;
  population_size: number;
  coverage: string;
  exclusions: CohortExclusions;
  outcomes: CohortOutcomeMetric[];
}

export interface CohortTrendTerm {
  id: string;
  year: number;
  season: string;
  label: string;
}

export interface CohortTrendOutcome {
  program_outcome_id: string | null;
  code: string;
  label: string;
  mean: string | null;
  median: string | null;
  n: number;
  population_size: number;
  coverage: string;
  exclusions: CohortExclusions;
}

export interface CohortTrendPoint {
  publication_id: string;
  run_id: string;
  term: CohortTrendTerm | null;
  term_id: string | null;
  po_set_version: number;
  series_version: number;
  policy_version: string;
  publication_status: PublicationStatus;
  published_at: string | null;
  sample_size: number;
  population_size: number;
  coverage: string;
  exclusions: CohortExclusions;
  outcomes: CohortTrendOutcome[];
}

export interface CohortTrendsResponse {
  program_id: string;
  po_set_version: number;
  points: CohortTrendPoint[];
}

export interface CohortProgramOption {
  id: string;
  label: string;
  department?: string;
}

export interface CohortTermOption {
  id: string;
  label: string;
}

export interface CohortCourseOption {
  id: string;
  label: string;
}

export interface CohortAnalyticsParams {
  programId: string;
  publicationId?: string;
  termId?: string;
  courseId?: string;
}

export interface CohortTrendsParams {
  programId: string;
  poSetVersion?: number;
  publicationIds?: string[];
}
