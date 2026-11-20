'use client';

import * as React from 'react';
import {
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Avatar, AvatarFallback } from './avatar';
import { BrandCrest } from './brand-crest';
import { Button } from './button';
import { ThemeToggle } from './theme-toggle';

export interface ShellNavItem {
  id: string;
  label: string;
  href: string;
  icon?: React.ReactNode;
  badge?: string;
  active?: boolean;
}

export interface ShellUser {
  name: string;
  subtitle?: string;
  initials: string;
  email?: string;
}

export interface RoleSidebarShellProps {
  workspaceLabel: string;
  brandSubtitle?: string;
  navItems: ShellNavItem[];
  user?: ShellUser;
  onSignOut?: () => void;
  signingOut?: boolean;
  signOutError?: string | null;
  defaultCollapsed?: boolean;
  children: React.ReactNode;
}

function useEscapeKey(active: boolean, onEscape: () => void) {
  React.useEffect(() => {
    if (!active) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onEscape();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [active, onEscape]);
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }
    const mql = window.matchMedia(query);
    const update = () => setMatches(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, [query]);

  return matches;
}

export function RoleSidebarShell({
  workspaceLabel,
  brandSubtitle = 'Acıbadem CSE',
  navItems,
  user,
  onSignOut,
  signingOut = false,
  signOutError = null,
  defaultCollapsed = false,
  children,
}: RoleSidebarShellProps) {
  const isTabletRail = useMediaQuery('(min-width: 768px) and (max-width: 1023px)');
  const [manualCollapsed, setManualCollapsed] = React.useState<boolean | null>(
    defaultCollapsed ? true : null,
  );
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const mobileTriggerRef = React.useRef<HTMLButtonElement | null>(null);

  const collapsed = manualCollapsed ?? isTabletRail;

  const closeMobile = React.useCallback(() => {
    setMobileOpen(false);
    mobileTriggerRef.current?.focus();
  }, []);

  useEscapeKey(mobileOpen, closeMobile);

  function renderNavList(isCompact: boolean, onNavigate?: () => void) {
    return (
      <nav
        aria-label={workspaceLabel}
        className="flex flex-col gap-1"
        data-slot="role-sidebar-nav"
      >
        {navItems.map((item) => {
          const isActive = Boolean(item.active);
          return (
            <a
              key={item.id}
              href={item.href}
              aria-current={isActive ? 'page' : undefined}
              title={isCompact ? item.label : undefined}
              onClick={onNavigate}
              data-slot="role-sidebar-nav-item"
              data-active={isActive ? 'true' : 'false'}
              className={cn(
                'relative flex min-h-9 items-center rounded-[var(--radius-input)] text-sm transition-[background-color,color] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 motion-reduce:transition-none',
                isCompact
                  ? 'justify-center px-0'
                  : 'justify-between gap-2.5 px-3 py-2',
                isActive
                  ? 'bg-[var(--accent-soft)] font-medium text-[var(--accent-primary)] before:absolute before:top-1.5 before:bottom-1.5 before:left-0 before:w-[3px] before:rounded-r-full before:bg-[var(--accent-primary)]'
                  : 'text-sidebar-foreground hover:bg-[var(--surface-hover)] hover:text-foreground',
              )}
            >
              <span
                className={cn(
                  'flex min-w-0 items-center',
                  isCompact ? 'justify-center' : 'gap-2.5',
                )}
              >
                {item.icon ? (
                  <span className="shrink-0 [&_svg]:size-4" aria-hidden="true">
                    {item.icon}
                  </span>
                ) : null}
                {isCompact ? (
                  <span className="sr-only">{item.label}</span>
                ) : (
                  <span className="truncate">{item.label}</span>
                )}
              </span>
              {!isCompact && item.badge ? (
                <span className="tabular-mono shrink-0 rounded-[var(--radius-tag)] bg-background/70 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {item.badge}
                </span>
              ) : null}
            </a>
          );
        })}
      </nav>
    );
  }

  function renderFooter(isCompact: boolean) {
    return (
      <div
        data-slot="role-sidebar-footer"
        className={cn(
          'mt-auto flex flex-col gap-2.5 border-t border-sidebar-border pt-3',
          isCompact ? 'items-center px-1.5' : 'px-3',
        )}
      >
        {user ? (
          <div
            className={cn(
              'flex items-center gap-2.5',
              isCompact ? 'justify-center' : 'min-w-0',
            )}
          >
            <Avatar size="sm" className="shrink-0">
              <AvatarFallback className="bg-[var(--accent-soft)] text-[11px] font-semibold text-[var(--accent-primary)]">
                {user.initials}
              </AvatarFallback>
            </Avatar>
            {!isCompact ? (
              <div className="min-w-0 flex-1 leading-tight">
                <p className="truncate text-[13px] font-medium text-foreground">
                  {user.name}
                </p>
                {user.subtitle ? (
                  <p className="truncate text-[11.5px] text-muted-foreground">
                    {user.subtitle}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <div
          className={cn(
            'flex items-center gap-1.5',
            isCompact ? 'flex-col' : 'justify-between',
          )}
        >
          <ThemeToggle
            showLabel={!isCompact}
            variant="ghost"
            size={isCompact ? 'icon-sm' : 'sm'}
            className={cn(!isCompact && 'flex-1 justify-start')}
          />
          {onSignOut ? (
            <Button
              type="button"
              variant="ghost"
              size={isCompact ? 'icon-sm' : 'sm'}
              disabled={signingOut}
              onClick={onSignOut}
              aria-label={signingOut ? 'Signing out' : 'Sign out'}
              title={isCompact ? 'Sign out' : undefined}
              className={cn(
                'text-muted-foreground hover:text-foreground',
                !isCompact && 'shrink-0',
              )}
            >
              <LogOut className="size-4" aria-hidden="true" />
              {isCompact ? (
                <span className="sr-only">Sign out</span>
              ) : (
                <span>{signingOut ? 'Signing out…' : 'Sign out'}</span>
              )}
            </Button>
          ) : null}
        </div>
        {signOutError && !isCompact ? (
          <p role="alert" className="text-xs text-destructive">
            {signOutError}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div
      data-slot="role-sidebar-shell"
      data-collapsed={collapsed ? 'true' : 'false'}
      className="flex min-h-svh w-full flex-col bg-background text-foreground md:flex-row"
    >
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      {/* Mobile top bar (<768px) */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border bg-sidebar px-4 md:hidden">
        <div className="flex min-w-0 items-center gap-2.5">
          <Button
            ref={mobileTriggerRef}
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Open navigation menu"
            aria-expanded={mobileOpen}
            aria-controls="mobile-sidebar-drawer"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-4" aria-hidden="true" />
          </Button>
          <BrandCrest size="sm" subtitle={brandSubtitle} />
        </div>
        <ThemeToggle variant="ghost" size="icon-sm" />
      </header>

      {/* Mobile off-canvas drawer (<768px) */}
      {mobileOpen ? (
        <div
          className="fixed inset-0 z-50 flex md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
          id="mobile-sidebar-drawer"
        >
          <div
            className="fixed inset-0 bg-black/45 transition-opacity duration-200 ease-out motion-reduce:transition-none"
            aria-hidden="true"
            onClick={closeMobile}
          />
          <aside className="relative z-10 flex h-full w-[264px] max-w-[85vw] flex-col border-r border-sidebar-border bg-sidebar py-4 shadow-lg">
            <div className="flex items-center justify-between gap-2 px-3 pb-4">
              <BrandCrest size="sm" subtitle={brandSubtitle} />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Close navigation menu"
                onClick={closeMobile}
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-2">
              <p className="px-2 pb-1.5 text-xs font-medium text-muted-foreground">
                {workspaceLabel}
              </p>
              {renderNavList(false, closeMobile)}
            </div>
            {renderFooter(false)}
          </aside>
        </div>
      ) : null}

      {/* Desktop / Tablet Tinted Navy Sidebar (240px expanded, 58px icon rail) */}
      <aside
        aria-label="Primary navigation"
        data-slot="role-sidebar"
        className={cn(
          'sticky top-0 hidden h-svh shrink-0 flex-col border-r border-sidebar-border bg-sidebar py-4 transition-[width] duration-200 ease-out motion-reduce:transition-none md:flex',
          collapsed ? 'w-[58px]' : 'w-[240px]',
        )}
      >
        <div
          className={cn(
            'flex items-center pb-4',
            collapsed ? 'flex-col gap-2 px-1.5' : 'justify-between gap-2 px-3',
          )}
        >
          <BrandCrest
            size="sm"
            subtitle={brandSubtitle}
            collapsed={collapsed}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setManualCollapsed(!collapsed)}
            className="shrink-0 text-muted-foreground hover:text-foreground"
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" aria-hidden="true" />
            ) : (
              <PanelLeftClose className="size-4" aria-hidden="true" />
            )}
          </Button>
        </div>

        <div className={cn('flex-1 overflow-y-auto', collapsed ? 'px-1.5' : 'px-2.5')}>
          {!collapsed ? (
            <p className="px-2.5 pb-1.5 text-xs font-medium text-muted-foreground">
              {workspaceLabel}
            </p>
          ) : null}
          {renderNavList(collapsed)}
        </div>

        {renderFooter(collapsed)}
      </aside>

      <main
        id="main-content"
        tabIndex={-1}
        className="min-w-0 flex-1 outline-none"
      >
        {children}
      </main>
    </div>
  );
}

export interface StudentTopNavShellProps {
  navItems: ShellNavItem[];
  user?: ShellUser;
  onSignOut?: () => void;
  signingOut?: boolean;
  signOutError?: string | null;
  children: React.ReactNode;
}

export function StudentTopNavShell({
  navItems,
  user,
  onSignOut,
  signingOut = false,
  signOutError = null,
  children,
}: StudentTopNavShellProps) {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement | null>(null);

  const closeMobile = React.useCallback(() => {
    setMobileOpen(false);
    triggerRef.current?.focus();
  }, []);

  useEscapeKey(mobileOpen, closeMobile);

  return (
    <div
      data-slot="student-topnav-shell"
      className="flex min-h-svh w-full flex-col bg-background text-foreground"
    >
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <header
        data-slot="student-topbar"
        className="sticky top-0 z-30 h-14 border-b border-border bg-card/95 backdrop-blur-xs"
      >
        <div className="mx-auto flex h-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-6">
            <BrandCrest size="sm" subtitle="Student portal" />

            <nav
              aria-label="Student navigation"
              className="hidden items-center gap-1 md:flex"
              data-slot="student-nav"
            >
              {navItems.map((item) => {
                const isActive = Boolean(item.active);
                return (
                  <a
                    key={item.id}
                    href={item.href}
                    aria-current={isActive ? 'page' : undefined}
                    data-slot="student-nav-tab"
                    data-active={isActive ? 'true' : 'false'}
                    className={cn(
                      'relative inline-flex h-9 items-center gap-2 rounded-[var(--radius-input)] px-3 text-sm transition-[background-color,color] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 motion-reduce:transition-none',
                      isActive
                        ? 'bg-[var(--accent-soft)] font-medium text-[var(--accent-primary)]'
                        : 'text-muted-foreground hover:bg-[var(--surface-hover)] hover:text-foreground',
                    )}
                  >
                    {item.icon ? (
                      <span className="shrink-0 [&_svg]:size-4" aria-hidden="true">
                        {item.icon}
                      </span>
                    ) : null}
                    <span>{item.label}</span>
                  </a>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle variant="ghost" size="icon-sm" />

            {user ? (
              <div className="hidden items-center gap-2 border-l border-border pl-2.5 sm:flex">
                <Avatar size="sm">
                  <AvatarFallback className="bg-[var(--accent-soft)] text-[11px] font-semibold text-[var(--accent-primary)]">
                    {user.initials}
                  </AvatarFallback>
                </Avatar>
                <span className="max-w-[140px] truncate text-[13px] font-medium text-foreground">
                  {user.name}
                </span>
              </div>
            ) : null}

            {onSignOut ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={signingOut}
                onClick={onSignOut}
                className="hidden text-muted-foreground hover:text-foreground md:inline-flex"
              >
                <LogOut className="size-4" aria-hidden="true" />
                <span>{signingOut ? 'Signing out…' : 'Sign out'}</span>
              </Button>
            ) : null}

            <Button
              ref={triggerRef}
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Open student navigation menu"
              aria-expanded={mobileOpen}
              aria-controls="student-mobile-drawer"
              onClick={() => setMobileOpen(true)}
              className="md:hidden"
            >
              <Menu className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </header>

      {signOutError ? (
        <div
          role="alert"
          className="border-b border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-2 text-center text-xs text-[var(--status-danger-fg)]"
        >
          {signOutError}
        </div>
      ) : null}

      {/* Mobile off-canvas drawer for Student (<768px) */}
      {mobileOpen ? (
        <div
          className="fixed inset-0 z-50 flex justify-end md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Student navigation menu"
          id="student-mobile-drawer"
        >
          <div
            className="fixed inset-0 bg-black/45 transition-opacity duration-200 ease-out motion-reduce:transition-none"
            aria-hidden="true"
            onClick={closeMobile}
          />
          <aside className="relative z-10 flex h-full w-[264px] max-w-[85vw] flex-col border-l border-border bg-card p-4 shadow-lg">
            <div className="flex items-center justify-between pb-4">
              <BrandCrest size="sm" subtitle="Student portal" />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Close student navigation menu"
                onClick={closeMobile}
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <nav
              aria-label="Student mobile navigation"
              className="flex flex-1 flex-col gap-1"
            >
              {navItems.map((item) => {
                const isActive = Boolean(item.active);
                return (
                  <a
                    key={item.id}
                    href={item.href}
                    aria-current={isActive ? 'page' : undefined}
                    onClick={closeMobile}
                    className={cn(
                      'relative flex min-h-10 items-center gap-2.5 rounded-[var(--radius-input)] px-3 text-sm transition-[background-color,color] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none',
                      isActive
                        ? 'bg-[var(--accent-soft)] font-medium text-[var(--accent-primary)] before:absolute before:top-1.5 before:bottom-1.5 before:left-0 before:w-[3px] before:rounded-r-full before:bg-[var(--accent-primary)]'
                        : 'text-muted-foreground hover:bg-[var(--surface-hover)] hover:text-foreground',
                    )}
                  >
                    {item.icon ? (
                      <span className="shrink-0 [&_svg]:size-4" aria-hidden="true">
                        {item.icon}
                      </span>
                    ) : null}
                    <span>{item.label}</span>
                  </a>
                );
              })}
            </nav>
            <div className="mt-auto border-t border-border pt-3">
              {user ? (
                <div className="mb-3 flex items-center gap-2.5">
                  <Avatar size="sm">
                    <AvatarFallback className="bg-[var(--accent-soft)] text-[11px] font-semibold text-[var(--accent-primary)]">
                      {user.initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 leading-tight">
                    <p className="truncate text-[13px] font-medium text-foreground">
                      {user.name}
                    </p>
                    {user.subtitle ? (
                      <p className="truncate text-[11.5px] text-muted-foreground">
                        {user.subtitle}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : null}
              {onSignOut ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={signingOut}
                  onClick={onSignOut}
                  className="w-full justify-start"
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  <span>{signingOut ? 'Signing out…' : 'Sign out'}</span>
                </Button>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8"
      >
        {children}
      </main>
    </div>
  );
}
