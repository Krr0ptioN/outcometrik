import { ApiError } from './errors';
import type { ApiErrorKind } from './types';

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  csrfToken?: string;
}
export async function request<T>(
  path: `/api/${string}`,
  options: RequestOptions = {},
): Promise<T> {
  if (!path.startsWith('/api/') || path.includes('\\'))
    throw new Error('Expected a same-origin API path');
  const { body, csrfToken, ...init } = options;
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (body !== undefined) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token =
      csrfToken ??
      (typeof document === 'undefined'
        ? undefined
        : document.cookie
            .split('; ')
            .find((c) => c.startsWith('csrftoken='))
            ?.slice(10));
    if (!token) throw new ApiError('forbidden', 0, 'A CSRF token is required');
    headers.set('X-CSRFToken', decodeURIComponent(token));
  }
  const signal = AbortSignal.any([
    AbortSignal.timeout(10_000),
    ...(init.signal ? [init.signal] : []),
  ]);
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      signal,
      method,
      headers,
      credentials: 'same-origin',
      redirect: 'error',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError('unavailable', 0);
  }
  let data: unknown = null;
  try {
    data = response.status === 204 ? null : await response.json();
  } catch {
    if (response.ok) throw new ApiError('unexpected', response.status);
  }
  if (!response.ok) {
    const kind: ApiErrorKind =
      response.status === 401
        ? 'unauthorized'
        : response.status === 403
          ? 'forbidden'
          : response.status === 400 || response.status === 422
            ? 'validation'
            : response.status === 409
              ? 'conflict'
              : response.status >= 500
                ? 'unavailable'
                : 'unexpected';
    throw new ApiError(kind, response.status, data);
  }
  return data as T;
}
