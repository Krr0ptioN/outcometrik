import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import {
  BrandCrest,
  RoleSidebarShell,
  StudentTopNavShell,
  ThemeProvider,
  type ShellNavItem,
} from '../index';

const adminNav: ShellNavItem[] = [
  { id: 'overview', label: 'Overview', href: '/admin', active: true },
  { id: 'academic', label: 'Academic catalog', href: '/admin/academic', badge: '4' },
];

const studentNav: ShellNavItem[] = [
  { id: 'profile', label: 'PO profile', href: '/student', active: true },
  { id: 'courses', label: 'My courses', href: '/student#courses' },
  { id: 'snapshots', label: 'Snapshots & reports', href: '/student#snapshots' },
];

describe('BrandCrest', () => {
  it('links home with accessible label and supports collapsed icon-only mode', () => {
    const expanded = renderToStaticMarkup(
      <BrandCrest subtitle="Acıbadem CSE" />,
    );
    expect(expanded).toContain('href="/"');
    expect(expanded).toContain('aria-label="Outcometrik home"');
    expect(expanded).toContain('Outcometrik');
    expect(expanded).toContain('Acıbadem CSE');
    expect(expanded).toContain('<svg');

    const collapsed = renderToStaticMarkup(
      <BrandCrest subtitle="Acıbadem CSE" collapsed />,
    );
    expect(collapsed).toContain('aria-label="Outcometrik home"');
    expect(collapsed).not.toContain('Acıbadem CSE');
  });
});

describe('RoleSidebarShell', () => {
  it('renders 240px tinted sidebar, 3px left-rail active indicator, skip link, footer controls, and no role switcher', () => {
    const html = renderToStaticMarkup(
      <ThemeProvider defaultTheme="light">
        <RoleSidebarShell
          workspaceLabel="Administrator workspace"
          navItems={adminNav}
          user={{
            name: 'System Administrator',
            subtitle: 'Institution Administrator',
            initials: 'SA',
          }}
          onSignOut={() => undefined}
        >
          <h1>Admin dashboard</h1>
        </RoleSidebarShell>
      </ThemeProvider>,
    );

    expect(html).toContain('href="#main-content"');
    expect(html).toContain('Skip to main content');
    expect(html).toContain('w-[240px]');
    expect(html).toContain('bg-sidebar');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('before:w-[3px]');
    expect(html).toContain('bg-[var(--accent-soft)]');
    expect(html).toContain('data-slot="theme-toggle"');
    expect(html).toContain('Sign out');
    expect(html).toContain('SA');
    expect(html).toContain('id="main-content"');
    expect(html).not.toContain('transition-all');
    expect(html).not.toContain('<select');
  });

  it('supports 58px collapsed icon rail mode with screen-reader labels', () => {
    const html = renderToStaticMarkup(
      <ThemeProvider defaultTheme="light">
        <RoleSidebarShell
          workspaceLabel="Instructor workspace"
          navItems={adminNav}
          defaultCollapsed
        >
          <p>Workspace</p>
        </RoleSidebarShell>
      </ThemeProvider>,
    );

    expect(html).toContain('w-[58px]');
    expect(html).toContain('data-collapsed="true"');
    expect(html).toContain('aria-label="Expand sidebar"');
    expect(html).toContain('<span class="sr-only">Overview</span>');
  });
});

describe('StudentTopNavShell', () => {
  it('renders 56px top bar with Outcometrik crest, 3 focused nav tabs, ThemeToggle, avatar, and sign-out', () => {
    const html = renderToStaticMarkup(
      <ThemeProvider defaultTheme="light">
        <StudentTopNavShell
          navItems={studentNav}
          user={{
            name: 'Deniz Aydın',
            subtitle: 'Student',
            initials: 'DA',
          }}
          onSignOut={() => undefined}
        >
          <h1>Program Outcome profile</h1>
        </StudentTopNavShell>
      </ThemeProvider>,
    );

    expect(html).toContain('h-14');
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('data-slot="brand-crest"');
    expect(html).toContain('PO profile');
    expect(html).toContain('My courses');
    expect(html).toContain('Snapshots &amp; reports');
    expect(html).toContain('aria-current="page"');
    expect(html).toContain('data-slot="theme-toggle"');
    expect(html).toContain('Deniz Aydın');
    expect(html).toContain('DA');
    expect(html).toContain('Sign out');
    expect(html).not.toContain('<select');
  });
});
