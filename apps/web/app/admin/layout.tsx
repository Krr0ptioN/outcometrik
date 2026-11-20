'use client';

import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { RoleWorkspaceShell } from '@outcometrik/access';

export default function AdminLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname() || '/admin';

  return (
    <RoleWorkspaceShell role="admin" currentPath={pathname}>
      {children}
    </RoleWorkspaceShell>
  );
}
