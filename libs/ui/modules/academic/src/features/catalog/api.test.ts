import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import { createCatalogRecord, getCatalogRows, parseCatalogPage } from './api';

afterEach(() => vi.unstubAllGlobals());

it('parses scoped academic API pages and rejects malformed rows', () => {
  const page = {
    count: 1,
    next: null,
    previous: null,
    results: [{ id: 'program-1', title: 'CSE' }],
  };
  expect(parseCatalogPage(page)).toEqual(page.results);
  expect(() =>
    parseCatalogPage({ results: [{ title: 'missing id' }] }),
  ).toThrow(ApiError);
});

it('loads an institution-filtered catalog with cancellation and no-store caching', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      Response.json({ count: 0, next: null, previous: null, results: [] }),
    );
  vi.stubGlobal('fetch', fetcher);
  const controller = new AbortController();
  await getCatalogRows(
    'departments',
    { institution: 'institution-a' },
    controller.signal,
  );
  const url = new URL(fetcher.mock.calls[0][0], 'http://localhost');
  expect(url.pathname).toBe('/api/v1/departments/');
  expect(url.searchParams.get('institution')).toBe('institution-a');
  expect(fetcher.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);
  expect(fetcher.mock.calls[0][1].cache).toBe('no-store');
  controller.abort();
  expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
});

it('loads every page when a catalog has more than 200 records', async () => {
  const fetcher = vi.fn().mockImplementation(async (url: string) => {
    const page = new URL(url, 'http://localhost').searchParams.get('page');
    return Response.json({
      count: 201,
      next: null,
      previous: null,
      results: [{ id: `program-${page}` }],
    });
  });
  vi.stubGlobal('fetch', fetcher);
  await expect(getCatalogRows('programs', {})).resolves.toHaveLength(2);
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('posts catalog data to the chosen resource endpoint', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ id: 'program-1' }, { status: 201 }));
  vi.stubGlobal('document', { cookie: 'csrftoken=test-token' });
  vi.stubGlobal('fetch', fetcher);
  await createCatalogRecord('programs', {
    department: 'department-1',
    code: 'CSE',
    title: 'Computer Engineering',
  });
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/programs/');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    department: 'department-1',
    code: 'CSE',
    title: 'Computer Engineering',
  });
  expect(fetcher.mock.calls[0][1].headers.get('X-CSRFToken')).toBe(
    'test-token',
  );
});
