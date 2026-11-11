import { ApiError, request } from '@outcometrik/api';
import {
  isRecord,
  isScope,
  isUser,
  type Scope,
  type User,
} from '../session/api';

export interface Role {
  slug: string;
  name: string;
  scope_kind: Scope['kind'];
}
export interface Assignment {
  id: string;
  user_id: number;
  scope_id: string;
  role_id?: string;
  capability_id?: string;
}
export interface Person extends User {
  roles: Assignment[];
  grants: Assignment[];
}
export interface Audit {
  id: string;
  action: string;
  actor: string;
  subject: string | null;
  scope_id: string;
  occurred_at: string;
}
export interface Dashboard {
  scope_id: string;
  scopes: Scope[];
  roles: Role[];
  capabilities: string[];
  users: Person[];
  counts: {
    users: number;
    roles: number;
    grants: number;
    scopes: number;
    programs: number;
    offerings: number;
  };
  total: number;
  page: number;
  page_size: number;
  audit: Audit[];
}
function isAssignment(value: unknown): value is Assignment {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.user_id === 'number' &&
    typeof value.scope_id === 'string' &&
    (typeof value.role_id === 'string' ||
      typeof value.capability_id === 'string')
  );
}
export function parseDashboard(value: unknown): Dashboard {
  if (
    !isRecord(value) ||
    typeof value.scope_id !== 'string' ||
    !Array.isArray(value.scopes) ||
    !value.scopes.every(isScope) ||
    !Array.isArray(value.roles) ||
    !value.roles.every(
      (v) =>
        isRecord(v) &&
        typeof v.slug === 'string' &&
        typeof v.name === 'string' &&
        ['institution', 'program', 'offering'].includes(String(v.scope_kind)),
    ) ||
    !Array.isArray(value.capabilities) ||
    !value.capabilities.every((v) => typeof v === 'string') ||
    !Array.isArray(value.users) ||
    !value.users.every(
      (v) =>
        isUser(v) &&
        isRecord(v) &&
        Array.isArray(v.roles) &&
        v.roles.every(isAssignment) &&
        Array.isArray(v.grants) &&
        v.grants.every(isAssignment),
    ) ||
    !isRecord(value.counts) ||
    !['users', 'roles', 'grants', 'scopes', 'programs', 'offerings'].every(
      (k) =>
        typeof value.counts === 'object' &&
        value.counts !== null &&
        isRecord(value.counts) &&
        typeof value.counts[k] === 'number',
    ) ||
    !['total', 'page', 'page_size'].every(
      (k) => typeof value[k] === 'number',
    ) ||
    !Array.isArray(value.audit) ||
    !value.audit.every(
      (v) =>
        isRecord(v) &&
        typeof v.id === 'string' &&
        typeof v.action === 'string' &&
        typeof v.actor === 'string' &&
        (v.subject === null || typeof v.subject === 'string') &&
        typeof v.scope_id === 'string' &&
        typeof v.occurred_at === 'string',
    )
  )
    throw new ApiError('unexpected', 200);
  return value as unknown as Dashboard;
}
export async function getDashboard(
  scope: string,
  search: string,
  page: number,
  signal?: AbortSignal,
) {
  return parseDashboard(
    await request(
      `/api/access/dashboard/?${new URLSearchParams({ scope, search, page: String(page) })}`,
      { signal, cache: 'no-store' },
    ),
  );
}
export interface AccountInput {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  scope: string;
  role: string;
}
export async function createAccount(body: AccountInput) {
  const data = await request('/api/access/accounts/', { method: 'POST', body });
  if (!isUser(data)) throw new ApiError('unexpected', 201);
  return data;
}
export async function createScope(body: {
  label: string;
  kind: string;
  parent: string;
}) {
  const data = await request('/api/access/scopes/', { method: 'POST', body });
  if (!isScope(data)) throw new ApiError('unexpected', 201);
  return data;
}
export async function assignAccess(body: {
  user: number;
  scope: string;
  role?: string;
  capability?: string;
}) {
  const data = await request('/api/access/assignments/', {
    method: 'POST',
    body,
  });
  if (!isRecord(data) || typeof data.id !== 'string')
    throw new ApiError('unexpected', 201);
}
export async function revokeAccess(kind: 'roles' | 'grants', id: string) {
  await request(`/api/access/${kind}/${id}/`, { method: 'DELETE' });
}
export async function activateAccount(id: number, password: string) {
  const data = await request(`/api/access/accounts/${id}/activate/`, {
    method: 'POST',
    body: { password },
  });
  if (!isUser(data)) throw new ApiError('unexpected', 200);
}
