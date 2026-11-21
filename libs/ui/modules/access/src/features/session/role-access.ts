import type { ShellUser } from '@outcometrik/ui';
import { defaultDashboard, type Session, type User } from './api';

export type WorkspaceRole = 'admin' | 'coordinator' | 'instructor' | 'student';

const ROLE_ROUTE_PREFIX: Record<WorkspaceRole, string> = {
  admin: '/admin',
  coordinator: '/coordinator',
  instructor: '/instructor',
  student: '/student',
};

const ROLE_SUBTITLE: Record<WorkspaceRole, string> = {
  admin: 'Institution Administrator',
  coordinator: 'Program Coordinator',
  instructor: 'Instructor',
  student: 'Student',
};

export function hasWorkspaceAccess(
  session: Pick<Session, 'user' | 'scopes' | 'roles'> | null | undefined,
  role: WorkspaceRole,
): boolean {
  if (!session?.user) return false;
  if (role === 'admin') {
    return session.scopes.some((scope) => scope.kind === 'institution');
  }
  const assignedRoles = new Set(session.roles.map((entry) => entry.role));
  if (role === 'coordinator') return assignedRoles.has('program-coordinator');
  if (role === 'instructor') return assignedRoles.has('instructor');
  if (role === 'student') return assignedRoles.has('student');
  return false;
}

export function isSafeInternalPath(path: string | null | undefined): path is string {
  if (!path) return false;
  return path.startsWith('/') && !path.startsWith('//') && !path.includes('\\');
}

export function workspaceRoleForPath(path: string): WorkspaceRole | null {
  for (const [role, prefix] of Object.entries(ROLE_ROUTE_PREFIX) as [
    WorkspaceRole,
    string,
  ][]) {
    if (path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`) || path.startsWith(`${prefix}#`)) {
      return role;
    }
  }
  return null;
}

/**
 * Returns the redirect target when a session cannot access `requiredRole`,
 * or `null` when the session is authorized.
 */
export function getUnauthorizedRedirect(
  session: Pick<Session, 'user' | 'scopes' | 'roles'> | null | undefined,
  requiredRole: WorkspaceRole,
  currentPath?: string,
): string | null {
  if (!session?.user) {
    if (isSafeInternalPath(currentPath) && currentPath !== '/login') {
      return `/login?next=${encodeURIComponent(currentPath)}`;
    }
    return '/login';
  }

  if (hasWorkspaceAccess(session, requiredRole)) {
    return null;
  }

  const fallback = defaultDashboard(session);
  return fallback !== '/' ? fallback : '/login?unauthorized=1';
}

export function resolvePostLoginRedirect(
  session: Pick<Session, 'user' | 'scopes' | 'roles'>,
  nextPath?: string | null,
): string {
  if (isSafeInternalPath(nextPath) && nextPath !== '/login') {
    const requiredRole = workspaceRoleForPath(nextPath);
    if (!requiredRole || hasWorkspaceAccess(session, requiredRole)) {
      return nextPath;
    }
  }
  return defaultDashboard(session);
}

export function formatShellUser(
  user: User,
  role: WorkspaceRole,
): ShellUser {
  const fullName = [user.first_name, user.last_name]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' ');
  const displayName = fullName || user.username;
  const parts = displayName.split(/\s+/).filter(Boolean);
  const initials =
    parts.length >= 2
      ? `${parts[0][0] ?? ''}${parts[parts.length - 1][0] ?? ''}`.toUpperCase()
      : displayName.slice(0, 2).toUpperCase();

  return {
    name: displayName,
    subtitle: ROLE_SUBTITLE[role],
    initials: initials || 'OU',
    email: user.email,
  };
}
