'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { SessionMenu, errorMessage, useSession } from '@outcometrik/access';
import {
  Button,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Separator,
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  Skeleton,
  ThemeToggle,
} from '@outcometrik/ui';

export type CoordinatorNavPath =
  | '/coordinator'
  | '/coordinator/analytics'
  | '/coordinator/approvals'
  | '/coordinator/po-sets'
  | '/coordinator/publications';

const NAV_ITEMS: ReadonlyArray<{
  href: CoordinatorNavPath;
  label: string;
  icon: ReactNode;
}> = [
  {
    href: '/coordinator',
    label: 'Overview',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4 shrink-0"
        aria-hidden="true"
      >
        <rect width="7" height="9" x="3" y="3" rx="1" />
        <rect width="7" height="5" x="14" y="3" rx="1" />
        <rect width="7" height="9" x="14" y="12" rx="1" />
        <rect width="7" height="5" x="3" y="16" rx="1" />
      </svg>
    ),
  },
  {
    href: '/coordinator/analytics',
    label: 'Cohort analytics & trends',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4 shrink-0"
        aria-hidden="true"
      >
        <path d="M3 3v18h18" />
        <path d="m19 9-5 5-4-4-3 3" />
      </svg>
    ),
  },
  {
    href: '/coordinator/approvals',
    label: 'Syllabus approvals & weights',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4 shrink-0"
        aria-hidden="true"
      >
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    href: '/coordinator/po-sets',
    label: 'PO1–PO11 set manager',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4 shrink-0"
        aria-hidden="true"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5Z" />
        <path d="m2 17 10 5 10-5" />
        <path d="m2 12 10 5 10-5" />
      </svg>
    ),
  },
  {
    href: '/coordinator/publications',
    label: 'Calculations & publications',
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-4 shrink-0"
        aria-hidden="true"
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="13" y2="17" />
      </svg>
    ),
  },
];

export interface CoordinatorShellProps {
  activePath: CoordinatorNavPath;
  title: string;
  description: string;
  children: ReactNode;
}

export function CoordinatorShell({
  activePath,
  title,
  description,
  children,
}: CoordinatorShellProps) {
  const session = useSession();
  const allowed = Boolean(
    session.data?.roles.some(
      (assignment) => assignment.role === 'program-coordinator',
    ),
  );

  if (session.isPending) {
    return (
      <main className="mx-auto max-w-6xl space-y-4 p-8" role="status">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  if (session.isError) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>
              <h1>Unable to load your session.</h1>
            </EmptyTitle>
            <EmptyDescription>
              <p role="alert">{errorMessage(session.error)}</p>
              <Button
                className="mt-3"
                onClick={() => void session.refetch()}
              >
                Try again
              </Button>
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </main>
    );
  }

  if (!session.data?.user) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>
              <h1>Sign in to continue.</h1>
            </EmptyTitle>
            <EmptyDescription>
              <Link
                href="/login"
                className="font-medium text-[var(--accent-primary)] underline-offset-4 hover:underline"
              >
                Go to sign in →
              </Link>
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </main>
    );
  }

  if (!allowed) {
    return (
      <main className="mx-auto flex min-h-svh max-w-lg items-center p-6">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>
              <h1>Program coordinator access required.</h1>
            </EmptyTitle>
            <EmptyDescription>
              <p>This account has no active program coordinator role.</p>
              <div className="mt-4">
                <SessionMenu />
              </div>
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </main>
    );
  }

  return (
    <SidebarProvider>
      <a className="skip-link" href="#coordinator-main">
        Skip to main content
      </a>
      <Sidebar role="complementary" aria-label="Coordinator governance navigation">
        <SidebarHeader className="border-b border-sidebar-border px-3 py-3">
          <Link
            href="/"
            className="flex items-center gap-2.5 rounded-md px-1 py-1 focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-[6px] bg-[var(--brand-mark-bg)] text-xs font-semibold text-[var(--brand-mark-fg)]"
              aria-hidden="true"
            >
              O
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-foreground">
                Outcometrik
              </p>
              <p className="truncate text-[11px] text-muted-foreground">
                Coordinator governance
              </p>
            </div>
          </Link>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Governance</SidebarGroupLabel>
            <SidebarMenu aria-label="Coordinator sections">
              {NAV_ITEMS.map((item) => {
                const isActive = item.href === activePath;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className={
                        isActive
                          ? 'rounded-l-none border-l-[3px] border-[var(--accent-primary)] bg-[var(--accent-soft)] font-medium text-[var(--accent-primary)]'
                          : 'border-l-[3px] border-transparent text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-foreground'
                      }
                    >
                      <Link
                        href={item.href}
                        aria-current={isActive ? 'page' : undefined}
                      >
                        {item.icon}
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter className="border-t border-sidebar-border p-3">
          <Button asChild variant="outline" size="sm" className="w-full">
            <Link href="/">All workspaces</Link>
          </Button>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset className="bg-[var(--surface-canvas)]">
        <header className="flex h-14 flex-wrap items-center justify-between gap-4 border-b border-border bg-[var(--surface-canvas)] px-6">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <Separator orientation="vertical" className="h-5" />
            <span className="text-sm font-medium text-muted-foreground">
              Coordinator governance
            </span>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <SessionMenu />
          </div>
        </header>

        <main
          id="coordinator-main"
          tabIndex={-1}
          className="mx-auto flex w-full max-w-[1380px] flex-col gap-6 p-6 lg:p-8"
        >
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
