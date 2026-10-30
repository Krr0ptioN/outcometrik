import type { ApiErrorKind } from './types';

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    public status: number,
    public details: unknown = null,
  ) {
    super(`API request failed: ${kind}`);
    this.name = 'ApiError';
  }
}
