import { ApiError, request } from '@outcometrik/api';
import { useQuery } from '@tanstack/react-query';

export interface HealthStatus {
  status?: 'ok' | 'unavailable';
}

export async function getHealth(signal?: AbortSignal): Promise<HealthStatus> {
  const data = await request<{ status: string }>('/api/health/status', {
    signal,
  });
  if (data?.status !== 'ok' && data?.status !== 'unavailable')
    throw new ApiError('unexpected', 200);
  return { status: data.status };
}


interface HealthQueryResult extends HealthStatus {
  message: string;
}

export const HEALTH_CHECK_ERROR_RESPONSE = {
  'unauthorized': 'Your session is required. Sign-in will be available when authentication is enabled.',
  'forbidden': 'Access denied. Your session may have expired.',
  'validation': 'The API rejected the request.',
  'conflict': 'The request conflicts with the current server state.',
  'unavailable': 'API unavailable. Please try again.',
  'unexpected': 'API unavailable. Please try again.',
};

export async function useHealthQuery(): Promise<HealthQueryResult> {
  'use client';

  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
  });
  let message = 'Checking API availability…';


  if (health.isError) {
    const kind =
      health.error instanceof ApiError ? health.error.kind : 'unexpected';
    message = HEALTH_CHECK_ERROR_RESPONSE[kind];


  } else if (health.isSuccess)
    message =
      health.data.status === 'ok'
        ? 'API available'
        : 'API unavailable. Please try again.';

  return { message, status: health.data?.status};
}
