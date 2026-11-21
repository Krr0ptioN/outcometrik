'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { RoleWorkspaceShell } from '@outcometrik/access';

export default function StudentLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname() || '/student';
  const [hash, setHash] = useState('');

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  return (
    <RoleWorkspaceShell
      role="student"
      currentPath={pathname}
      currentHash={hash}
    >
      {children}
    </RoleWorkspaceShell>
  );
}
