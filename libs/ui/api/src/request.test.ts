import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './index';
afterEach(() => vi.unstubAllGlobals());
describe('API client', () => {
  it('sends same-origin requests with session credentials', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ status: 'ok' }));
    vi.stubGlobal('fetch', fetch);
    await expect(request('/api/health/status')).resolves.toEqual({
      status: 'ok',
    });
    expect(fetch).toHaveBeenCalledWith(
      '/api/health/status',
      expect.objectContaining({ credentials: 'same-origin' }),
    );
  });
  it.each([
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [400, 'validation'],
    [422, 'validation'],
    [409, 'conflict'],
    [503, 'unavailable'],
  ])('normalizes %i', async (status, kind) => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: 'error' }, { status: Number(status) }),
        ),
    );
    await expect(request('/api/example')).rejects.toMatchObject({
      kind,
      status,
      details: { detail: 'error' },
    });
  });
  it('requires CSRF for mutations and sends an explicit token', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetch);
    await expect(
      request('/api/example', { method: 'POST' }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetch).not.toHaveBeenCalled();
    await expect(
      request('/api/example', {
        method: 'POST',
        csrfToken: 'token',
        body: { score: '1.25' },
      }),
    ).resolves.toBeNull();
    expect(fetch.mock.calls[0][1].headers.get('X-CSRFToken')).toBe('token');
    expect(fetch.mock.calls[0][1].body).toBe('{"score":"1.25"}');
  });
});
