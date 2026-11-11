import { afterEach, expect, it, vi } from 'vitest';
import { getDashboard, parseDashboard } from './api';
const dashboard = {
  scope_id: 'institution-a',
  scopes: [],
  roles: [],
  capabilities: [],
  users: [],
  counts: {
    users: 0,
    roles: 0,
    grants: 0,
    scopes: 0,
    programs: 0,
    offerings: 0,
  },
  total: 0,
  page: 1,
  page_size: 20,
  audit: [],
};
afterEach(() => vi.unstubAllGlobals());
it('validates nested dashboard data before displaying it', () => {
  expect(parseDashboard(dashboard)).toEqual(dashboard);
  for (const value of [
    { ...dashboard, users: [{ id: 1 }] },
    { ...dashboard, counts: { users: '5' } },
    { ...dashboard, audit: [{ action: 'created' }] },
    {
      ...dashboard,
      roles: [{ slug: 'admin', name: 'Admin', scope_kind: 'global' }],
    },
  ])
    expect(() => parseDashboard(value)).toThrow();
});
it('encodes the institution, search and page in every request', async () => {
  const fetcher = vi
    .fn()
    .mockImplementation(async () => Response.json(dashboard));
  vi.stubGlobal('fetch', fetcher);
  await getDashboard('institution-a', 'Ada & Grace', 2);
  const url = new URL(fetcher.mock.calls[0][0], 'http://localhost');
  expect(url.searchParams.get('scope')).toBe('institution-a');
  expect(url.searchParams.get('search')).toBe('Ada & Grace');
  expect(url.searchParams.get('page')).toBe('2');
});
