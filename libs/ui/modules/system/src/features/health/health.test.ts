import { afterEach, describe, expect, it, vi } from 'vitest';
import { getHealth } from './index';
afterEach(() => vi.unstubAllGlobals());
describe('health client', () => {
  it('handles network failure and invalid successful health payloads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(getHealth()).rejects.toMatchObject({ kind: 'unavailable' });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ status: 'other' })),
    );
    await expect(getHealth()).rejects.toMatchObject({ kind: 'unexpected' });
  });
  it('returns the validated service status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(Response.json({ status: 'ok' })),
    );
    await expect(getHealth()).resolves.toEqual({ status: 'ok' });
  });
});
