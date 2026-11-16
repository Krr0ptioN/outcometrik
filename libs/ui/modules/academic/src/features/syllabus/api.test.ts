import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  changeSyllabus,
  getProgramOutcomeSets,
  getProgramOutcomes,
  getSyllabi,
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
