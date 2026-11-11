import { ApiError, request } from '@outcometrik/api';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
}
export interface Scope {
  id: string;
  kind: 'institution' | 'program' | 'offering';
  label: string;
  parent_id: string | null;
}
export interface Session {
  user: User | null;
  scopes: Scope[];
  roles: { role: string; scope: Scope }[];
}
export function defaultDashboard(session: Pick<Session, 'scopes' | 'roles'>): string {
  if (session.scopes.some((scope) => scope.kind === 'institution')) return '/admin';
  const roles = new Set(session.roles.map((assignment) => assignment.role));
  if (roles.has('program-coordinator')) return '/coordinator';
  if (roles.has('instructor')) return '/instructor';
  if (roles.has('student')) return '/student';
  return '/';
}
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
export function isUser(value: unknown): value is User {
  return (
    isRecord(value) &&
    typeof value.id === 'number' &&
    typeof value.username === 'string' &&
    typeof value.email === 'string' &&
    typeof value.first_name === 'string' &&
    typeof value.last_name === 'string' &&
    typeof value.is_active === 'boolean'
  );
}
export function isScope(value: unknown): value is Scope {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.label === 'string' &&
    ['institution', 'program', 'offering'].includes(String(value.kind)) &&
    (value.parent_id === null || typeof value.parent_id === 'string')
  );
}
export function parseSession(data: unknown): Session {
  if (
    !isRecord(data) ||
    (data.user !== null && !isUser(data.user)) ||
    !Array.isArray(data.scopes) ||
    !data.scopes.every(isScope) ||
    !Array.isArray(data.roles) ||
    !data.roles.every(
      (assignment) =>
        isRecord(assignment) &&
        typeof assignment.role === 'string' &&
        isScope(assignment.scope),
    )
  )
    throw new ApiError('unexpected', 200);
  return { user: data.user, scopes: data.scopes, roles: data.roles } as Session;
}
export async function getSession(signal?: AbortSignal) {
  return parseSession(
    await request('/api/auth/session/', { signal, cache: 'no-store' }),
  );
}
export async function signIn(username: string, password: string) {
  await getSession(); // Establish the CSRF cookie before an anonymous login POST.
  return parseSession(
    await request('/api/auth/login/', {
      method: 'POST',
      body: { username, password },
    }),
  );
}
export async function signOut() {
  await request('/api/auth/logout/', { method: 'POST' });
}
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError))
    return 'Something went wrong. Please try again.';
  if (error.kind === 'forbidden')
    return 'Access denied. Refresh the page and sign in again if your session expired.';
  if (error.status === 429)
    return 'Too many attempts. Please wait a minute before trying again.';
  if (error.kind === 'unavailable')
    return 'Unable to reach the server. Please try again.';
  if (error.kind === 'validation') {
    const detail = error.details;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.every((v) => typeof v === 'string'))
      return detail.join(' ');
    if (isRecord(detail)) {
      const messages = Object.entries(detail).flatMap(([key, value]) => {
        const text =
          typeof value === 'string'
            ? value
            : Array.isArray(value)
              ? value.filter((v) => typeof v === 'string').join(' ')
              : '';
        return text
          ? [
              `${key === 'detail' || key === 'non_field_errors' ? '' : `${key}: `}${text}`,
            ]
          : [];
      });
      if (messages.length) return messages.join(' ');
    }
  }
  return 'The request could not be completed. Please try again.';
}
