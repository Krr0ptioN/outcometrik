import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import { getGradeBatches, getGrades } from './api';

afterEach(() => vi.unstubAllGlobals());

const batch = (id: string) => ({
  id,
  offering: 'offering-1',
  name: `Batch ${id}`,
  released_at: null,
  created_at: '2026-01-01T00:00:00Z',
});

it('retrieves all grade batches without following untrusted pagination URLs', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        next: 'https://example.invalid/next',
        previous: null,
        results: [batch('1')],
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        next: null,
        previous: 'previous',
        results: [batch('2')],
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  const controller = new AbortController();

  expect(
    (await getGradeBatches('offering-1', controller.signal)).map(
      (item) => item.id,
    ),
  ).toEqual(['1', '2']);
  expect(fetcher.mock.calls[1][0]).toBe(
    '/api/v1/grade-batches/?offering=offering-1&page_size=200&page=2',
  );
  expect(fetcher.mock.calls[1][1].signal).toBeInstanceOf(AbortSignal);
});

it('rejects inconsistent pagination instead of silently omitting grades', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        count: 1,
        next: 'next',
        previous: null,
        results: [],
      }),
    ),
  );
  await expect(getGrades('offering-1')).rejects.toBeInstanceOf(ApiError);
});
