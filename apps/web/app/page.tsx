'use client';

import Link from 'next/link';
import { defaultDashboard, SessionMenu, useSession } from '@outcometrik/access';
import { useHealthQuery } from '@outcometrik/system';
import { Button } from './ui/button';

export default function Home() {
  const health = useHealthQuery();
  const session = useSession();
  const roles = new Set(session.data?.roles.map((assignment) => assignment.role));
  const dashboards = [
    ...(session.data?.scopes.some((scope) => scope.kind === 'institution')
      ? [{ label: 'Institution administrator', href: '/admin' }]
      : []),
    ...(roles.has('program-coordinator')
      ? [{ label: 'Program coordinator', href: '/coordinator' }]
      : []),
    ...(roles.has('instructor')
      ? [{ label: 'Instructor', href: '/instructor' }]
      : []),
    ...(roles.has('student') ? [{ label: 'Student', href: '/student' }] : []),
  ];

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="topbar">
          <Link className="brand" href="/" aria-label="Outcometrik home">
            Outcometrik
          </Link>
          <nav aria-label="Primary navigation">
            <a href="#status">System status</a>
            <SessionMenu />
          </nav>
        </header>
        <section className="hero" aria-labelledby="page-title">
          <p className="eyebrow">Outcome measurement workspace</p>
          <h1 id="page-title">Outcometrik</h1>
          <p className="lede">
            A role-aware workspace for your institution, courses, and learning
            outcomes.
          </p>
        </section>
        <section
          id="status"
          className="status-card"
          aria-labelledby="status-title"
        >
          <div>
            <p className="eyebrow">Connection</p>
            <h2 id="status-title">API availability</h2>
          </div>
          <p role="status" aria-live="polite" aria-busy={health.isFetching}>
            {health.message}
          </p>
          <Button
            onClick={() => void health.refetch()}
            disabled={health.isFetching}
          >
            {health.isFetching ? 'Checking…' : 'Check again'}
          </Button>
        </section>
        <section
          id="workspace"
          className="workspace"
          aria-labelledby="workspace-title"
        >
          <p className="eyebrow">Your workspace</p>
          <h2 id="workspace-title">
            {session.data?.user
              ? `Welcome, ${session.data.user.first_name || session.data.user.username}.`
              : 'Choose a dashboard to get started.'}
          </h2>
          {session.isPending ? (
            <p role="status">Loading your roles…</p>
          ) : dashboards.length ? (
            <nav aria-label="Available dashboards" className="flex flex-wrap gap-3">
              {dashboards.map((dashboard) => (
                <Button asChild key={dashboard.href}>
                  <Link href={dashboard.href}>{dashboard.label}</Link>
                </Button>
              ))}
            </nav>
          ) : (
            <p>
              {session.data?.user
                ? 'No dashboard is assigned to this account yet. Contact your institution administrator.'
                : 'Sign in to see the dashboards assigned to your account.'}
            </p>
          )}
          {session.data?.user && (
            <p className="mt-3 text-sm text-muted-foreground">
              Default view: {defaultDashboard(session.data)}
            </p>
          )}
        </section>
      </main>
    </>
  );
}
