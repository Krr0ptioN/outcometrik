'use client';

import Link from 'next/link';
import { useHealthQuery } from '@outcometrik/system';
import { Button } from './ui/button';

export default function Home() {
  const health = useHealthQuery();

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
          </nav>
        </header>
        <section className="hero" aria-labelledby="page-title">
          <p className="eyebrow">Outcome measurement workspace</p>
          <h1 id="page-title">Outcometrik</h1>
          <p className="lede">
            A clear view of learning outcomes. Domain workflows will appear here
            as they become available.
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
          <p className="eyebrow">Next step</p>
          <h2 id="workspace-title">Your workspace is waiting.</h2>
          <p>
            No courses to display yet. Course navigation will appear here as
            features become available.
          </p>
        </section>
      </main>
    </>
  );
}
