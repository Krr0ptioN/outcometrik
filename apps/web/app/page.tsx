'use client';
import { Button } from './ui/button';

export default function Home() {
  const health = useHealthQuery();

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header>
        <span className="font-semibold">Outcometrik</span>
        <nav aria-label="Main navigation">
          <a href="#main" aria-current="page">
            Overview
          </a>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <p className="text-sm text-slate-600">Workspace foundation</p>
        <h1>Outcometrik</h1>
        <section aria-labelledby="health-title">
          <h2 id="health-title">Service status</h2>
          <p role="status" aria-live="polite" aria-busy={health.isFetching}>
            {message}
          </p>
          <Button
            onClick={() => void health.refetch()}
            disabled={health.isFetching}
          >
            {health.isFetching ? 'Checking…' : 'Check again'}
          </Button>
        </section>
        <section aria-labelledby="workspace-title">
          <h2 id="workspace-title">Your workspace</h2>
          <p>
            No courses to display yet. Course navigation will appear here as
            features become available.
          </p>
        </section>
      </main>
    </>
  );
}
