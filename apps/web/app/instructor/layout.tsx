'use client';

import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { RoleWorkspaceShell } from '@outcometrik/access';

export default function InstructorLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname() || '/instructor';

  return (
    <RoleWorkspaceShell role="instructor" currentPath={pathname}>
      {children}
    </RoleWorkspaceShell>
  );
}
