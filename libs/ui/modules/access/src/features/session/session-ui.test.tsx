import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from '@outcometrik/ui';
import { SignIn } from './components';
import {
  DEMO_PERSONAS,
  getDemoPersonaPassword,
  isDemoPersonasEnabled,
  validateSignInFields,
} from './personas';
import {
  formatShellUser,
  getUnauthorizedRedirect,
  hasWorkspaceAccess,
  isSafeInternalPath,
  resolvePostLoginRedirect,
} from './role-access';
import { RoleWorkspaceShell } from './role-shell';
import type { Session } from './api';

const baseUser = {
  id: 1,
  username: 'selin.kaya@acibadem.edu.tr',
  email: 'selin.kaya@acibadem.edu.tr',
  first_name: 'Selin',
  last_name: 'Kaya',
  is_active: true,
};

const institutionScope = {
  id: 'inst-1',
  kind: 'institution' as const,
  label: 'Acıbadem University',
  parent_id: null,
};

const programScope = {
  id: 'prog-1',
  kind: 'program' as const,
  label: 'B.Sc. Computer Engineering',
  parent_id: 'inst-1',
};

const offeringScope = {
  id: 'off-1',
  kind: 'offering' as const,
  label: 'CSE 311-01',
  parent_id: 'prog-1',
};

function renderWithProviders(element: React.ReactElement, session?: Session) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  if (session !== undefined) {
    client.setQueryData(['session'], session);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ThemeProvider defaultTheme="light">{element}</ThemeProvider>
    </QueryClientProvider>,
  );
}

describe('login form validation', () => {
  it('requires both institutional email/username and password', () => {
    expect(validateSignInFields('', '')).toEqual({
      username: 'Enter your institutional email or username.',
      password: 'Enter your password.',
    });
    expect(validateSignInFields('   ', 'secret')).toEqual({
      username: 'Enter your institutional email or username.',
    });
    expect(validateSignInFields('admin@acibadem.edu.tr', '')).toEqual({
      password: 'Enter your password.',
    });
    expect(validateSignInFields('admin@acibadem.edu.tr', 'secret')).toEqual({});
  });

  it('rejects overlong username and password inputs', () => {
    expect(validateSignInFields('a'.repeat(151), 'secret').username).toContain(
      '150 characters',
    );
    expect(
      validateSignInFields('admin@acibadem.edu.tr', 'x'.repeat(1025)).password,
    ).toContain('maximum allowed length');
  });

  it('renders split-pane recipe-auth form with specific CTA, password toggle, and tinted navy proof panel', () => {
    const html = renderWithProviders(
      <SignIn onSignedIn={() => undefined} showDemoPersonas={false} />,
    );

    expect(html).toContain('data-slot="auth-split-shell"');
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('Institutional email');
    expect(html).toContain('Password');
    expect(html).toContain('aria-label="Show password"');
    expect(html).toContain('Continue to workspace');
    expect(html).toContain('data-slot="auth-proof-pane"');
    expect(html).toContain('Verified cohort attainment');
    expect(html).toContain('81.2');
    expect(html).toContain('ROUND_HALF_UP');
    expect(html).not.toContain('data-slot="demo-persona-switcher"');
    expect(html).not.toContain('font-serif');
  });
});

describe('dev-only persona switcher gating', () => {
  it('hides personas in production unless NEXT_PUBLIC_ENABLE_DEMO_PERSONAS=true', () => {
    expect(
      isDemoPersonasEnabled({ nodeEnv: 'production', enableDemoPersonas: undefined }),
    ).toBe(false);
    expect(
      isDemoPersonasEnabled({ nodeEnv: 'production', enableDemoPersonas: 'false' }),
    ).toBe(false);
    expect(
      isDemoPersonasEnabled({ nodeEnv: 'production', enableDemoPersonas: 'true' }),
    ).toBe(true);
    expect(
      isDemoPersonasEnabled({ nodeEnv: 'development', enableDemoPersonas: undefined }),
    ).toBe(true);
    expect(
      isDemoPersonasEnabled({ nodeEnv: 'development', enableDemoPersonas: 'false' }),
    ).toBe(false);
  });

  it('renders all 4 seeded persona cards when enabled and omits them when disabled', () => {
    const enabledHtml = renderWithProviders(
      <SignIn onSignedIn={() => undefined} showDemoPersonas={true} />,
    );
    expect(enabledHtml).toContain('data-slot="demo-persona-switcher"');
    expect(enabledHtml).toContain('or sign in as a seeded persona');
    for (const persona of DEMO_PERSONAS) {
      expect(enabledHtml).toContain(`data-persona="${persona.id}"`);
      expect(enabledHtml).toContain(persona.name);
    }

    const disabledHtml = renderWithProviders(
      <SignIn onSignedIn={() => undefined} showDemoPersonas={false} />,
    );
    expect(disabledHtml).not.toContain('data-slot="demo-persona-switcher"');
    expect(disabledHtml).not.toContain('data-persona="admin"');
  });

  it('resolves demo password with explicit override > env > local default', () => {
    expect(getDemoPersonaPassword('custom-pass', 'env-pass')).toBe('custom-pass');
    expect(getDemoPersonaPassword('', 'env-pass')).toBe('env-pass');
    expect(getDemoPersonaPassword('', undefined)).toBe(
      'choose-a-local-demo-password',
    );
  });
});

describe('unauthorized redirect and role access', () => {
  const anonymous: Session = { user: null, scopes: [], roles: [] };
  const studentSession: Session = {
    user: baseUser,
    scopes: [],
    roles: [{ role: 'student', scope: offeringScope }],
  };
  const instructorSession: Session = {
    user: baseUser,
    scopes: [],
    roles: [{ role: 'instructor', scope: offeringScope }],
  };
  const coordinatorSession: Session = {
    user: baseUser,
    scopes: [],
    roles: [{ role: 'program-coordinator', scope: programScope }],
  };
  const adminSession: Session = {
    user: baseUser,
    scopes: [institutionScope],
    roles: [],
  };

  it('redirects anonymous users to /login preserving safe next path', () => {
    expect(getUnauthorizedRedirect(anonymous, 'admin', '/admin')).toBe(
      '/login?next=%2Fadmin',
    );
    expect(getUnauthorizedRedirect(anonymous, 'student', '/student')).toBe(
      '/login?next=%2Fstudent',
    );
    expect(getUnauthorizedRedirect(anonymous, 'admin', '//evil.example')).toBe(
      '/login',
    );
  });

  it('redirects authenticated users lacking role permission to their authorized dashboard', () => {
    expect(getUnauthorizedRedirect(studentSession, 'admin', '/admin')).toBe(
      '/student',
    );
    expect(
      getUnauthorizedRedirect(instructorSession, 'coordinator', '/coordinator'),
    ).toBe('/instructor');
    expect(getUnauthorizedRedirect(adminSession, 'admin', '/admin')).toBeNull();
    expect(
      getUnauthorizedRedirect(coordinatorSession, 'coordinator', '/coordinator'),
    ).toBeNull();
    expect(
      getUnauthorizedRedirect(instructorSession, 'instructor', '/instructor'),
    ).toBeNull();
    expect(
      getUnauthorizedRedirect(studentSession, 'student', '/student'),
    ).toBeNull();
  });

  it('validates safe internal paths and prevents open redirects after login', () => {
    expect(isSafeInternalPath('/instructor/gradebook')).toBe(true);
    expect(isSafeInternalPath('//evil.com')).toBe(false);
    expect(isSafeInternalPath('https://evil.com')).toBe(false);
    expect(isSafeInternalPath('/\\evil')).toBe(false);

    expect(
      resolvePostLoginRedirect(instructorSession, '/instructor/gradebook'),
    ).toBe('/instructor/gradebook');
    expect(resolvePostLoginRedirect(studentSession, '/admin')).toBe('/student');
    expect(resolvePostLoginRedirect(adminSession, '//evil.com')).toBe('/admin');
  });

  it('evaluates workspace access and formats user initials accurately', () => {
    expect(hasWorkspaceAccess(adminSession, 'admin')).toBe(true);
    expect(hasWorkspaceAccess(studentSession, 'admin')).toBe(false);
    expect(formatShellUser(baseUser, 'instructor')).toEqual({
      name: 'Selin Kaya',
      subtitle: 'Instructor',
      initials: 'SK',
      email: 'selin.kaya@acibadem.edu.tr',
    });
  });

  it('renders RoleSidebarShell for faculty/admin and StudentTopNavShell for student', () => {
    const instructorHtml = renderWithProviders(
      <RoleWorkspaceShell
        role="instructor"
        workspaceLabel="Instructor workspace"
        navItems={[
          { id: 'home', label: 'My courses & mapping', href: '/instructor', active: true },
          { id: 'gradebook', label: 'Gradebook', href: '/instructor/gradebook' },
        ]}
      >
        <p>Instructor body</p>
      </RoleWorkspaceShell>,
      instructorSession,
    );
    expect(instructorHtml).toContain('data-slot="role-sidebar-shell"');
    expect(instructorHtml).toContain('Instructor body');
    expect(instructorHtml).not.toContain('<select');

    const studentHtml = renderWithProviders(
      <RoleWorkspaceShell
        role="student"
        navItems={[
          { id: 'profile', label: 'PO profile', href: '/student', active: true },
          { id: 'courses', label: 'My courses', href: '/student#courses' },
          { id: 'snapshots', label: 'Snapshots & reports', href: '/student#snapshots' },
        ]}
      >
        <p>Student body</p>
      </RoleWorkspaceShell>,
      studentSession,
    );
    expect(studentHtml).toContain('data-slot="student-topnav-shell"');
    expect(studentHtml).toContain('Student body');
    expect(studentHtml).not.toContain('<select');
  });
});
