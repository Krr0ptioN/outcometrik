import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import type {
  CohortAnalyticsResponse,
  CohortTrendsResponse,
  CoordinatorPublication,
} from './types';

const mockQueries = vi.hoisted(() => ({
  programs: { data: [] as unknown[], isPending: false, isError: false, error: null as unknown },
  terms: { data: [] as unknown[], isPending: false, isError: false, error: null as unknown },
  courses: { data: [] as unknown[], isPending: false, isError: false, error: null as unknown },
  publications: {
    data: [] as CoordinatorPublication[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  analytics: {
    data: undefined as CohortAnalyticsResponse | undefined,
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  trends: {
    data: undefined as CohortTrendsResponse | undefined,
    isPending: false,
    isError: false,
    error: null as unknown,
  },
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
    const key = queryKey[1];
    if (key === 'cohort-programs') return mockQueries.programs;
    if (key === 'cohort-terms') return mockQueries.terms;
    if (key === 'cohort-courses') return mockQueries.courses;
    if (key === 'coordinator-publications') return mockQueries.publications;
    if (key === 'cohort-analytics') return mockQueries.analytics;
    if (key === 'cohort-trends') return mockQueries.trends;
    return { data: undefined, isPending: false, isError: false, error: null };
  },
}));

import { CohortOverview } from './components/cohort-overview';

const PROGRAM_ID = '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55';
const PUBLICATION_ID = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const RUN_ID = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';

const PROGRAMS = [{ id: PROGRAM_ID, label: 'CSE-BS · Computer Engineering' }];
const TERMS = [{ id: 'term-1', label: '2025 Fall' }];
const COURSES = [{ id: 'course-1', label: 'CSE301 · Algorithms' }];

const PUB_V1: CoordinatorPublication = {
  id: PUBLICATION_ID,
  program: PROGRAM_ID,
  offering: null,
  term: 'term-1',
  run: RUN_ID,
  series_version: 1,
  po_set_version: 1,
  audience: 'faculty',
  published_at: '2026-01-20T10:00:00Z',
  stale: false,
};

const ZERO_AND_UNASSESSED_ANALYTICS: CohortAnalyticsResponse = {
  publication_id: PUBLICATION_ID,
  run_id: RUN_ID,
  series_version: 1,
  program_id: PROGRAM_ID,
  offering_id: null,
  term_id: 'term-1',
  po_set_version: 1,
  policy_version: 'policy-2026-v1',
  engine_version: 'calc-v1',
  publication_status: 'published',
  audience: 'faculty',
  published_at: '2026-01-20T10:00:00Z',
  filters: { course_id: null, term_id: null },
  sample_size: 1,
  population_size: 2,
  coverage: '0.5000',
  exclusions: {
    NOT_ASSESSED: 1,
    INCOMPLETE: 0,
    ALL_EXEMPT: 0,
    UNMAPPED: 0,
  },
  outcomes: [
    {
      program_outcome_id: 'po-1',
      code: 'PO-1',
      label: 'Engineering Fundamentals',
      n: 1,
      population_size: 2,
      coverage: '0.5000',
      mean: '0.0',
      median: '0.0',
      min: '0.0',
      max: '0.0',
      distribution: {
        '<50': 1,
        '50-69.9': 0,
        '70-84.9': 0,
        '85-100': 0,
      },
      exclusions: {
        NOT_ASSESSED: 1,
        INCOMPLETE: 0,
        ALL_EXEMPT: 0,
        UNMAPPED: 0,
      },
    },
  ],
};

beforeEach(() => {
  mockQueries.programs = { data: PROGRAMS, isPending: false, isError: false, error: null };
  mockQueries.terms = { data: TERMS, isPending: false, isError: false, error: null };
  mockQueries.courses = { data: COURSES, isPending: false, isError: false, error: null };
  mockQueries.publications = { data: [PUB_V1], isPending: false, isError: false, error: null };
  mockQueries.analytics = {
    data: ZERO_AND_UNASSESSED_ANALYTICS,
    isPending: false,
    isError: false,
    error: null,
  };
  mockQueries.trends = { data: undefined, isPending: false, isError: false, error: null };
});

describe('CohortOverview component', () => {
  it('distinguishes measured zero (0.0, n=1) from 1 unassessed student with traceability metadata', () => {
    const markup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );

    // Traceability header
    expect(markup).toContain(PUBLICATION_ID);
    expect(markup).toContain('Publication 8f0d3c3e');
    expect(markup).toContain('Run 1c2d3e4f');
    expect(markup).toContain('PO-Set v1');
    expect(markup).toContain('Policy policy-2026-v1');
    expect(markup).toContain('Published');

    // Acceptance scenario: measured zero 0.0 for n = 1 (1 / 2, 50% coverage) + 1 unassessed exclusion
    expect(markup).toContain('Mean: 0.0');
    expect(markup).toContain('n = 1 (1 / 2)');
    expect(markup).toContain('50%');
    expect(markup).toContain('Not assessed: 1');

    // Equivalent accessible data table with scope="col", scope="row", caption, and 0-100 scale
    expect(markup).toContain('<caption');
    expect(markup).toContain('scope="col"');
    expect(markup).toContain('scope="row"');
    expect(markup).toContain('0–100');
    expect(markup).toContain('1 / 0 / 0 / 0');
  });

  it('renders completely unassessed PO (n=0) as — Not assessed and never 0.0', () => {
    mockQueries.analytics = {
      data: {
        ...ZERO_AND_UNASSESSED_ANALYTICS,
        sample_size: 0,
        population_size: 2,
        coverage: '0.0000',
        exclusions: {
          NOT_ASSESSED: 2,
          INCOMPLETE: 0,
          ALL_EXEMPT: 0,
          UNMAPPED: 0,
        },
        outcomes: [
          {
            program_outcome_id: 'po-2',
            code: 'PO-2',
            label: 'System Design',
            n: 0,
            population_size: 2,
            coverage: '0.0000',
            mean: null,
            median: null,
            min: null,
            max: null,
            distribution: {
              '<50': 0,
              '50-69.9': 0,
              '70-84.9': 0,
              '85-100': 0,
            },
            exclusions: {
              NOT_ASSESSED: 2,
              INCOMPLETE: 0,
              ALL_EXEMPT: 0,
              UNMAPPED: 0,
            },
          },
        ],
      },
      isPending: false,
      isError: false,
      error: null,
    };

    const markup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );

    expect(markup).toContain('— Not assessed');
    expect(markup).toContain('0 / 2');
    expect(markup).toContain('Not assessed: 2');
    expect(markup).not.toContain('Mean: 0.0');
    expect(markup).not.toContain('role="img"');
  });

  it('surfaces an accessible role="alert" when trends fail due to incompatible PO-set versions', () => {
    mockQueries.trends = {
      data: undefined,
      isPending: false,
      isError: true,
      error: new ApiError('validation', 400, {
        code: 'incompatible_po_set_version',
        detail:
          'Cannot compare publications with different PO-set versions; changed PO definitions are not a performance trend.',
      }),
    };

    const markup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
        defaultShowTrends: true,
      }),
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain('Trend comparison unavailable');
    expect(markup).toContain('incompatible PO-set versions');
  });

  it('renders loading, empty (404), and scope-denied (403) states safely without PII', () => {
    // Loading state
    mockQueries.analytics = {
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
    };
    const loadingMarkup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );
    expect(loadingMarkup).toContain('role="status"');
    expect(loadingMarkup).toContain('Loading cohort analytics');

    // Empty (404) state
    mockQueries.analytics = {
      data: undefined,
      isPending: false,
      isError: true,
      error: new ApiError('unexpected', 404, {
        detail: 'student_secret@example.edu',
      }),
    };
    const emptyMarkup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );
    expect(emptyMarkup).toContain('No published cohort analytics available');
    expect(emptyMarkup).not.toContain('student_secret@example.edu');

    // Scope-denied (403) state
    mockQueries.analytics = {
      data: undefined,
      isPending: false,
      isError: true,
      error: new ApiError('forbidden', 403, {
        detail: 'Forbidden for student_secret@example.edu',
      }),
    };
    const forbiddenMarkup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );
    expect(forbiddenMarkup).toContain('role="alert"');
    expect(forbiddenMarkup).toContain(
      'You do not have permission to view cohort analytics for this scope.',
    );
    expect(forbiddenMarkup).not.toContain('student_secret@example.edu');
  });

  it('renders stale publication status badge and alert warning', () => {
    mockQueries.analytics = {
      data: {
        ...ZERO_AND_UNASSESSED_ANALYTICS,
        publication_status: 'stale',
      },
      isPending: false,
      isError: false,
      error: null,
    };

    const markup = renderToStaticMarkup(
      createElement(CohortOverview, {
        programs: PROGRAMS,
        terms: TERMS,
        courses: COURSES,
      }),
    );

    expect(markup).toContain('Stale');
    expect(markup).toContain('Stale publication snapshot');
    expect(markup).toContain('role="alert"');
  });
});
