export type UUID = string & { readonly __brand: 'UUID' };
export type UtcTimestamp = string & { readonly __brand: 'UtcTimestamp' };
export type DecimalString = string & { readonly __brand: 'DecimalString' };
export type Nullable<T> = T | null;

export interface HealthStatus { status: 'ok' | 'unavailable'; }
export interface PaginationMeta { page: number; pageSize: number; total: number; }
export interface Paginated<T> { items: T[]; pagination: PaginationMeta; }
export interface ValidationErrorDetail { field: string; message: string; code: string; }
export interface ApiErrorPayload { detail?: string; errors?: ValidationErrorDetail[]; }

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly payload: ApiErrorPayload = {}) {
    super(payload.detail ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
  }
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: { Accept: 'application/json', ...init?.headers },
  });
  const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload & T;
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload as T;
}

export function getHealthStatus(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health/status');
}
