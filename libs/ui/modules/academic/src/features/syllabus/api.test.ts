import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  changeSyllabus,
  deleteSyllabusPOContribution,
  getProgramOutcomeSets,
  getProgramOutcomes,
  getSyllabi,
  getSyllabusPOContributions,
  saveSyllabusPOContribution,
} from './api';

afterEach(() => vi.unstubAllGlobals());
const syllabus = {
  id: 's1',
  offering: 'o1',
  version: 1,
  status: 'draft',
  approved_at: null,
  po_set_version: 1,
  learning_outcomes: [],
  assessments: [],
  po_contributions: [
    {
      id: 'c1',
      program_outcome: 'po1',
      program_outcome_code: 'PO1',
      weight: 5,
    },
  ],
};
it('loads and validates all syllabus pages for an offering', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ results: [syllabus], next: 'next' }))
    .mockResolvedValueOnce(
      Response.json({
        results: [{ ...syllabus, id: 's2', version: 2 }],
        next: null,
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  expect((await getSyllabi('o1')).map((item) => item.version)).toEqual([1, 2]);
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/syllabi/?offering=o1&page=2');
});
it('rejects malformed syllabus and outcome set responses', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ results: [{ id: 'bad' }], next: null }),
      ),
  );
  await expect(getSyllabi('o1')).rejects.toBeInstanceOf(ApiError);
  await expect(getProgramOutcomeSets('p1')).rejects.toBeInstanceOf(ApiError);
});
it('rejects syllabus with out-of-range or decimal course-to-PO weights', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        results: [
          {
            ...syllabus,
            po_contributions: [
              {
                id: 'c-bad',
                program_outcome: 'po1',
                program_outcome_code: 'PO1',
                weight: 3.5,
              },
            ],
          },
        ],
        next: null,
      }),
    ),
  );
  await expect(getSyllabi('o1')).rejects.toBeInstanceOf(ApiError);
});
it('loads, saves, updates, and deletes course-to-PO contribution weights', async () => {
  const contrib = {
    id: 'c1',
    program_outcome: 'po1',
    program_outcome_code: 'PO1',
    weight: 4,
  };
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json([contrib]))
    .mockResolvedValueOnce(Response.json(contrib))
    .mockResolvedValueOnce(Response.json({ ...contrib, weight: 5 }))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=token' });

  const loaded = await getSyllabusPOContributions('s1');
  expect(loaded).toEqual([contrib]);
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/syllabi/s1/po-contributions/');

  const created = await saveSyllabusPOContribution('s1', {
    program_outcome: 'po1',
    weight: 4,
  });
  expect(created.weight).toBe(4);
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/syllabi/s1/po-contributions/');
  expect(fetcher.mock.calls[1][1].method).toBe('POST');

  const updated = await saveSyllabusPOContribution(
    's1',
    { program_outcome: 'po1', weight: 5 },
    'c1',
  );
  expect(updated.weight).toBe(5);
  expect(fetcher.mock.calls[2][0]).toBe(
    '/api/v1/syllabi/s1/po-contributions/c1/',
  );
  expect(fetcher.mock.calls[2][1].method).toBe('PATCH');

  await deleteSyllabusPOContribution('s1', 'c1');
  expect(fetcher.mock.calls[3][0]).toBe(
    '/api/v1/syllabi/s1/po-contributions/c1/',
  );
  expect(fetcher.mock.calls[3][1].method).toBe('DELETE');
});
it('sends scoped child edits with CSRF protection', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({}));
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=token' });
  await changeSyllabus('s1/learning-outcomes/l1/', { code: 'LO1' }, 'PATCH');
  expect(fetcher.mock.calls[0][0]).toBe(
    '/api/v1/syllabi/s1/learning-outcomes/l1/',
  );
  expect(fetcher.mock.calls[0][1].method).toBe('PATCH');
  expect(fetcher.mock.calls[0][1].headers.get('X-CSRFToken')).toBe('token');
});

it('loads and validates outcome definitions before activation', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json([
        {
          id: 'p1',
          code: 'PO1',
          order: 1,
          label: 'Knowledge',
          description: 'Describe knowledge',
          source_reference: 'Policy',
        },
      ]),
    )
    .mockResolvedValueOnce(Response.json([{ id: 'p2', code: 'PO2' }]));
  vi.stubGlobal('fetch', fetcher);
  expect((await getProgramOutcomes('set1'))[0].code).toBe('PO1');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/po-sets/set1/outcomes/');
  await expect(getProgramOutcomes('set1')).rejects.toBeInstanceOf(ApiError);
});
