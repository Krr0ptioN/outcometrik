import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  cohortErrorMessage,
  formatCoveragePercent,
  getCohortAnalytics,
  getCohortTrends,
  getCoordinatorPublications,
} from './api';
import type {
  CohortAnalyticsResponse,
  CohortTrendsResponse,
  CoordinatorPublication,
} from './types';

const PROGRAM_ID = '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55';
const PUBLICATION_ID = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const PUBLICATION_ID_2 = '9a1e4d4f-7b2c-4d8f-ae22-3c6a5b8d0f12';
const RUN_ID = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';
const TERM_ID = '2d3e4f5a-6b7c-4d8e-9f0a-1b2c3d4e5f6a';
const COURSE_ID = '3e4f5a6b-7c8d-4e9f-0a1b-2c3d4e5f6a7b';

const validPublication: CoordinatorPublication = {
  id: PUBLICATION_ID,
  program: PROGRAM_ID,
  offering: null,
  term: TERM_ID,
  run: RUN_ID,
  series_version: 1,
  po_set_version: 1,
  audience: 'faculty',
  published_at: '2026-01-20T10:00:00Z',
  stale: false,
};

const validCohortResponse: CohortAnalyticsResponse = {
  publication_id: PUBLICATION_ID,
  run_id: RUN_ID,
  series_version: 1,
  program_id: PROGRAM_ID,
  offering_id: null,
  term_id: TERM_ID,
  po_set_version: 1,
  policy_version: 'policy-v1',
  engine_version: 'calc-v1',
  publication_status: 'published',
  audience: 'faculty',
  published_at: '2026-01-20T10:00:00Z',
  filters: {
    course_id: COURSE_ID,
    term_id: TERM_ID,
  },
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
      program_outcome_id: 'po-1-id',
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

const validTrendsResponse: CohortTrendsResponse = {
  program_id: PROGRAM_ID,
  po_set_version: 1,
  points: [
    {
      publication_id: PUBLICATION_ID,
      run_id: RUN_ID,
      term: {
        id: TERM_ID,
        year: 2025,
        season: 'fall',
        label: '2025-fall',
      },
      term_id: TERM_ID,
      po_set_version: 1,
      series_version: 1,
      policy_version: 'policy-v1',
      publication_status: 'published',
      published_at: '2026-01-20T10:00:00Z',
      sample_size: 4,
      population_size: 4,
      coverage: '1.0000',
      exclusions: {
        NOT_ASSESSED: 0,
        INCOMPLETE: 0,
        ALL_EXEMPT: 0,
        UNMAPPED: 0,
      },
      outcomes: [
        {
          program_outcome_id: 'po-1-id',
          code: 'PO-1',
          label: 'Engineering Fundamentals',
          mean: '67.5',
          median: '70.0',
          n: 4,
          population_size: 4,
          coverage: '1.0000',
          exclusions: {
            NOT_ASSESSED: 0,
            INCOMPLETE: 0,
            ALL_EXEMPT: 0,
            UNMAPPED: 0,
          },
        },
      ],
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJsonFetch(body: unknown, status = 200) {
  const fetcher = vi.fn(() => Promise.resolve(Response.json(body, { status })));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

describe('cohort-overview api', () => {
  it('fetches coordinator publications with no-store and unwraps paginated results', async () => {
    const fetcher = stubJsonFetch({
      count: 1,
      next: null,
      previous: null,
      results: [validPublication],
    });
    const controller = new AbortController();
    const result = await getCoordinatorPublications(
      PROGRAM_ID,
      controller.signal,
    );
    expect(result).toEqual([validPublication]);
    const [url, init] = fetcher.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(`/api/v1/publications/?program=${PROGRAM_ID}`);
    expect(init.cache).toBe('no-store');
  });

  it('rejects malformed coordinator publication payloads with ApiError(unexpected, 200)', async () => {
    stubJsonFetch({ results: [{ id: 123, stale: 'no' }] });
    await expect(getCoordinatorPublications(PROGRAM_ID)).rejects.toMatchObject({
      kind: 'unexpected',
      status: 200,
    });
  });

  it('fetches cohort analytics with scoped query params and no-store', async () => {
    const fetcher = stubJsonFetch(validCohortResponse);
    const result = await getCohortAnalytics({
      programId: PROGRAM_ID,
      publicationId: PUBLICATION_ID,
      termId: TERM_ID,
      courseId: COURSE_ID,
    });
    expect(result).toEqual(validCohortResponse);
    const [url, init] = fetcher.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      `/api/v1/analytics/cohort/?program_id=${PROGRAM_ID}&publication_id=${PUBLICATION_ID}&term_id=${TERM_ID}&course_id=${COURSE_ID}`,
    );
    expect(init.cache).toBe('no-store');
  });

  it('rejects malformed cohort analytics payloads with ApiError(unexpected, 200)', async () => {
    stubJsonFetch({
      ...validCohortResponse,
      publication_status: 'draft',
    });
    const err = await getCohortAnalytics({ programId: PROGRAM_ID }).catch(
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).kind).toBe('unexpected');
    expect((err as ApiError).status).toBe(200);
  });

  it('fetches cohort trends with po_set_version and publication_ids and no-store', async () => {
    const fetcher = stubJsonFetch(validTrendsResponse);
    const result = await getCohortTrends({
      programId: PROGRAM_ID,
      poSetVersion: 1,
      publicationIds: [PUBLICATION_ID, PUBLICATION_ID_2],
    });
    expect(result).toEqual(validTrendsResponse);
    const [url, init] = fetcher.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      `/api/v1/analytics/trends/?program_id=${PROGRAM_ID}&po_set_version=1&publication_ids=${PUBLICATION_ID}%2C${PUBLICATION_ID_2}`,
    );
    expect(init.cache).toBe('no-store');
  });

  it('rejects malformed cohort trends payloads with ApiError(unexpected, 200)', async () => {
    stubJsonFetch({ program_id: PROGRAM_ID, points: 'not-an-array' });
    await expect(
      getCohortTrends({ programId: PROGRAM_ID }),
    ).rejects.toMatchObject({
      kind: 'unexpected',
      status: 200,
    });
  });

  it('formats coverage percentages and maps safe error messages', () => {
    expect(formatCoveragePercent('0.5000')).toBe('50%');
    expect(formatCoveragePercent('0.3333')).toBe('33.3%');
    expect(formatCoveragePercent('1.0000')).toBe('100%');
    expect(formatCoveragePercent('0.0000')).toBe('0%');

    expect(
      cohortErrorMessage(
        new ApiError('validation', 400, {
          code: 'incompatible_po_set_version',
        }),
      ),
    ).toContain('incompatible PO-set versions');

    expect(cohortErrorMessage(new ApiError('forbidden', 403))).toContain(
      'permission',
    );
    expect(cohortErrorMessage(new ApiError('unexpected', 404))).toContain(
      'No published cohort analytics available',
    );
  });
});
