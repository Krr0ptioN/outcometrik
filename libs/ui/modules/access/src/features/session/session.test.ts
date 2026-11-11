import { afterEach, describe, expect, it, vi } from 'vitest';
import { defaultDashboard, errorMessage, getSession, parseSession, signIn, signOut } from './api';
import { ApiError } from '@outcometrik/api';
afterEach(() => vi.unstubAllGlobals());
describe('session contract', () => {
  it('accepts anonymous sessions and rejects malformed identity or scope data', () => {
    expect(parseSession({ user: null, scopes: [], roles: [] })).toEqual({
      user: null,
      scopes: [],
      roles: [],
    });
    for (const data of [
      null,
      {},
      { user: { id: 1 }, scopes: [], roles: [] },
      { user: null, scopes: [{ id: 'x', kind: 'global' }], roles: [] },
      { user: null, scopes: [], roles: [{ role: 'student', scope: {} }] },
    ])
      expect(() => parseSession(data)).toThrow(ApiError);
  });
  it('routes each role and prefers the most privileged assigned dashboard', () => {
    const scope = { id: 'x', kind: 'offering', label: 'CSE 301', parent_id: null } as const;
    expect(defaultDashboard({ scopes: [], roles: [{ role: 'student', scope }] })).toBe('/student');
    expect(defaultDashboard({ scopes: [], roles: [{ role: 'instructor', scope }] })).toBe('/instructor');
    expect(defaultDashboard({ scopes: [], roles: [{ role: 'program-coordinator', scope: { ...scope, kind: 'program' } }] })).toBe('/coordinator');
    expect(defaultDashboard({ scopes: [{ ...scope, kind: 'institution', parent_id: null }], roles: [{ role: 'student', scope }] })).toBe('/admin');
  });
  it('establishes a CSRF cookie before login and uses same-origin credentials', async () => {
    vi.stubGlobal('document', { cookie: 'csrftoken=test-csrf' });
    const fetcher = vi
      .fn()
      .mockImplementation(async () =>
        Response.json({ user: null, scopes: [], roles: [] }),
      );
    vi.stubGlobal('fetch', fetcher);
    await signIn('institution.admin', 'secret');
    expect(fetcher.mock.calls[0][0]).toBe('/api/auth/session/');
    expect(fetcher.mock.calls[1][0]).toBe('/api/auth/login/');
    const init = fetcher.mock.calls[1][1];
    expect(init.credentials).toBe('same-origin');
    expect(init.headers.get('X-CSRFToken')).toBe('test-csrf');
    expect(JSON.parse(init.body)).toEqual({
      username: 'institution.admin',
      password: 'secret',
    });
  });
  it('forwards cancellation to session requests and protects logout', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(Response.json({ user: null, scopes: [], roles: [] }));
    vi.stubGlobal('fetch', fetcher);
    const controller = new AbortController();
    await getSession(controller.signal);
    expect(fetcher.mock.calls[0][1].cache).toBe('no-store');
    controller.abort();
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true);
    await expect(signOut()).rejects.toMatchObject({ kind: 'forbidden' });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it('shows safe server validation and network messages', () => {
    expect(
      errorMessage(
        new ApiError('validation', 400, { username: ['Already in use.'] }),
      ),
    ).toContain('Already in use.');
    expect(errorMessage(new ApiError('unexpected', 429))).toContain(
      'Too many attempts',
    );
    expect(errorMessage(new ApiError('unavailable', 0))).toContain(
      'Unable to reach',
    );
  });
});
