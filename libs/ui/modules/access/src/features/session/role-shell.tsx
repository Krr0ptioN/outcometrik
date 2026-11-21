'use client';

import * as React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AwardIcon,
  BarChart3Icon,
  BookOpenIcon,
  ClipboardCheckIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  UsersIcon,
} from 'lucide-react';
import {
  RoleSidebarShell,
  Skeleton,
  StudentTopNavShell,
  type ShellNavItem,
} from '@outcometrik/ui';
import { errorMessage, signOut } from './api';
import { useSession } from './components';
import {
  formatShellUser,
  getUnauthorizedRedirect,
  type WorkspaceRole,
} from './role-access';

export interface RoleWorkspaceShellProps {
  role: WorkspaceRole;
  workspaceLabel?: string;
  brandSubtitle?: string;
  navItems?: ShellNavItem[];
  currentPath?: string;
  currentHash?: string;
  onRedirect?: (target: string) => void;
  children: React.ReactNode;
}

const DEFAULT_WORKSPACE_LABELS: Record<WorkspaceRole, string> = {
  admin: 'Administrator workspace',
  coordinator: 'Coordinator workspace',
  instructor: 'Instructor workspace',
  student: 'Student portal',
};

export function buildDefaultRoleNav(
  role: WorkspaceRole,
  currentPath = '',
  currentHash = '',
): ShellNavItem[] {
  if (role === 'admin') {
    return [
      {
        id: 'overview',
        label: 'Overview',
        href: '/admin',
        icon: <LayoutDashboardIcon />,
        active: currentPath === '/admin' || currentPath === '',
      },
      {
        id: 'academic',
        label: 'Academic catalog',
        href: '/admin/academic',
        icon: <BookOpenIcon />,
        active: currentPath.startsWith('/admin/academic'),
      },
    ];
  }

  if (role === 'coordinator') {
    return [
      {
        id: 'overview',
        label: 'Cohort overview',
        href: '/coordinator',
        icon: <BarChart3Icon />,
        active:
          (currentPath === '/coordinator' || currentPath === '') &&
          currentHash !== '#program-access',
      },
      {
        id: 'access',
        label: 'Program access',
        href: '/coordinator#program-access',
        icon: <UsersIcon />,
        active:
          currentPath === '/coordinator' && currentHash === '#program-access',
      },
    ];
  }

  if (role === 'instructor') {
    return [
      {
        id: 'courses',
        label: 'My courses & mapping',
        href: '/instructor',
        icon: <BookOpenIcon />,
        active: currentPath === '/instructor' || currentPath === '',
      },
      {
        id: 'gradebook',
        label: 'Gradebook',
        href: '/instructor/gradebook',
        icon: <ClipboardCheckIcon />,
        active: currentPath.startsWith('/instructor/gradebook'),
      },
    ];
  }

  return [
    {
      id: 'profile',
      label: 'PO profile',
      href: '/student',
      icon: <AwardIcon />,
      active:
        (currentPath === '/student' || currentPath === '') &&
        currentHash !== '#courses' &&
        currentHash !== '#snapshots',
    },
    {
      id: 'courses',
      label: 'My courses',
      href: '/student#courses',
      icon: <BookOpenIcon />,
      active: currentPath === '/student' && currentHash === '#courses',
    },
    {
      id: 'snapshots',
      label: 'Snapshots & reports',
      href: '/student#snapshots',
      icon: <FileTextIcon />,
      active: currentPath === '/student' && currentHash === '#snapshots',
    },
  ];
}

export function RoleWorkspaceShell({
  role,
  workspaceLabel,
  brandSubtitle = 'Acıbadem CSE',
  navItems,
  currentPath,
  currentHash = '',
  onRedirect,
  children,
}: RoleWorkspaceShellProps) {
  const session = useSession();
  const client = useQueryClient();

  const logout = useMutation({
    mutationFn: signOut,
    onSuccess: async () => {
      await client.cancelQueries();
      client.clear();
      if (onRedirect) {
        onRedirect('/login');
      } else {
        window.location.assign('/login');
      }
    },
  });

  const redirectTarget = session.isSuccess
    ? getUnauthorizedRedirect(session.data, role, currentPath)
    : null;

  React.useEffect(() => {
    if (!redirectTarget) return;
    if (onRedirect) {
      onRedirect(redirectTarget);
    } else if (typeof window !== 'undefined') {
      window.location.replace(redirectTarget);
    }
  }, [redirectTarget, onRedirect]);

  const resolvedNavItems =
    navItems ?? buildDefaultRoleNav(role, currentPath, currentHash);

  const user = session.data?.user
    ? formatShellUser(session.data.user, role)
    : undefined;

  const signOutError = logout.isError ? errorMessage(logout.error) : null;

  const content = session.isPending ? (
    <div
      className="mx-auto flex max-w-5xl flex-col gap-5 p-6 sm:p-8"
      role="status"
      aria-label="Loading workspace"
    >
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-36 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  ) : redirectTarget ? (
    <div
      className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-2 p-6 text-center"
      role="status"
    >
      <p className="text-sm font-medium text-foreground">
        Redirecting to your authorized workspace…
      </p>
      <a
        href={redirectTarget}
        className="text-sm text-[var(--accent-primary)] underline-offset-4 hover:underline"
      >
        Continue manually
      </a>
    </div>
  ) : (
    children
  );

  if (role === 'student') {
    return (
      <StudentTopNavShell
        navItems={resolvedNavItems}
        user={user}
        onSignOut={() => logout.mutate()}
        signingOut={logout.isPending}
        signOutError={signOutError}
      >
        {content}
      </StudentTopNavShell>
    );
  }

  return (
    <RoleSidebarShell
      workspaceLabel={workspaceLabel ?? DEFAULT_WORKSPACE_LABELS[role]}
      brandSubtitle={brandSubtitle}
      navItems={resolvedNavItems}
      user={user}
      onSignOut={() => logout.mutate()}
      signingOut={logout.isPending}
      signOutError={signOutError}
    >
      {content}
    </RoleSidebarShell>
  );
}
