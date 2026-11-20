import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  buildPublishIdempotencyKey,
  parsePublicationConflict,
  resolvePublicationFreshness,
  type GovernancePublication,
} from './publications-api';

const { PUB_V1, PUB_V2, mockQueries } = vi.hoisted(() => {
  const pubV1: GovernancePublication = {
    id: '11111111-1111-4111-8111-111111111111',
    program: 'prog-1',
    offering: null,
    offering_label: null,
    term: 'term-1',
    term_label: '2025 Fall',
    run: 'run-1',
    scope_kind: 'program',
    series_version: 1,
    po_set_version: 2,
    audience: 'faculty',
    input_hash: 'abcdef1234567890abcdef1234567890',
    idempotency_key: 'pub-prog-1-run-1-v1-faculty',
    published_at: '2026-01-15T10:00:00Z',
    stale: true,
  };

  const pubV2: GovernancePublication = {
    ...pubV1,
    id: '22222222-2222-4222-8222-222222222222',
    run: 'run-2',
    series_version: 2,
    input_hash: '9876543210fedcba9876543210fedcba',
    idempotency_key: 'pub-prog-1-run-2-v2-faculty',
    published_at: '2026-02-01T12:00:00Z',
    stale: false,
  };

  return {
    PUB_V1: pubV1,
    PUB_V2: pubV2,
    mockQueries: {
      workspace: {
        data: {
          programs: [
            { id: 'prog-1', label: 'CSE-BS · Computer Engineering', department: 'CSE' },
          ],
          offerings: [
            {
              id: 'off-1',
              program_id: 'prog-1',
              label: 'CSE 311-01',
              course: 'Database Systems',
              term: '2025 Fall',
              enrolled: 40,
            },
          ],
          students: [],
        },
        isPending: false,
        isError: false,
        error: null,
      },
      poSets: {
        data: [
          {
            id: 'set-2',
            version: 2,
            active: true,
            activated_at: '2026-01-10T00:00:00Z',
            effective_date: '2026-01-10',
            source_reference: 'MÜDEK 2026',
          },
        ],
        isPending: false,
        isError: false,
        error: null,
      },
      syllabi: {
        data: [
          {
            id: 'syl-1',
            offering: 'off-1',
            version: 1,
            status: 'approved',
            approved_at: '2026-01-12T00:00:00Z',
            po_set_version: 2,
            learning_outcomes: [],
            assessments: [],
          },
        ],
        isPending: false,
        isError: false,
        error: null,
      },
      terms: {
        data: [{ id: 'term-1', year: 2025, season: 'fall' }],
        isPending: false,
        isError: false,
        error: null,
      },
      runs: {
        data: [
          {
            id: 'run-2',
            scope_kind: 'program',
            program: 'prog-1',
            offering: null,
            po_set_version: 2,
            engine_version: 'calc-v1',
            policy_version: 'policy-2026-v1',
            input_hash: '9876543210fedcba9876543210fedcba',
            manifest: {},
            status: 'completed',
            is_complete_for_publication: true,
            error_detail: '',
            completed_at: '2026-02-01T11:59:00Z',
            created_at: '2026-02-01T11:58:00Z',
          },
        ],
        isPending: false,
        isError: false,
        error: null,
      },
      publications: {
        data: [pubV2, pubV1],
        isPending: false,
        isError: false,
        error: null,
      },
    },
  };
});

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  }),
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
    const key = queryKey[1];
    if (key === 'coordinator') return mockQueries.workspace;
    if (key === 'po-sets') return mockQueries.poSets;
    if (key === 'syllabi') return mockQueries.syllabi;
    if (key === 'terms') return mockQueries.terms;
    if (key === 'calculation-runs') return mockQueries.runs;
    if (key === 'publications') return mockQueries.publications;
    return { data: undefined, isPending: false, isError: false, error: null };
  },
}));

import { CoordinatorPublicationsManager } from './publications-manager';

describe('publications-api helpers', () => {
  it('marks Series v1 as stale when it is the only publication and stale=true', () => {
    expect(resolvePublicationFreshness(PUB_V1, [PUB_V1])).toBe('stale');
  });

  it('marks Series v2 as current and preserves Series v1 as historical after publishing v2', () => {
    expect(resolvePublicationFreshness(PUB_V2, [PUB_V2, PUB_V1])).toBe('current');
    expect(resolvePublicationFreshness(PUB_V1, [PUB_V2, PUB_V1])).toBe(
      'historical',
    );
  });

  it('builds deterministic idempotency keys for series publication', () => {
    expect(
      buildPublishIdempotencyKey({
        programId: 'prog-1234567890',
        runId: 'run-9876543210',
        expectedSeriesVersion: 1,
        audience: 'faculty',
      }),
    ).toBe('pub-prog-123-run-9876-v2-faculty');
  });

  it('parses HTTP 409 stale-input publication conflicts cleanly', () => {
    const err = new ApiError('conflict', 409, {
      code: 'stale_input',
      detail: 'Grades changed after calculation run completed.',
    });
    expect(parsePublicationConflict(err)).toEqual({
      isConflict: true,
      code: 'stale_input',
      message: 'Grades changed after calculation run completed.',
    });
  });
});

describe('CoordinatorPublicationsManager', () => {
  it('renders readiness gates, Run calculation & publish Series v3 CTA, and immutable publication series table', () => {
    const markup = renderToStaticMarkup(
      createElement(CoordinatorPublicationsManager),
    );

    expect(markup).toContain('Pre-publication readiness gates');
    expect(markup).toContain('Active PO1–PO11 set');
    expect(markup).toContain('Approved syllabi');
    expect(markup).toContain('Run calculation &amp; publish Series v3');
    expect(markup).toContain('Series v2');
    expect(markup).toContain('Series v1');
    expect(markup).toContain('Current');
    expect(markup).toContain('Historical');
    expect(markup).toContain('9876543210fe');
  });
});
