'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { ApiError, getHealthStatus } from '../lib/api';

export default function Home() {
  const health = useQuery({ queryKey: ['health-status'], queryFn: getHealthStatus });
  const error = health.error as ApiError | null;

  return <main className="shell">
    <header className="topbar">
      <Link className="brand" href="/" aria-label="CSE-3XX home">CSE-3XX</Link>
      <nav aria-label="Primary navigation"><a href="#status">System status</a><a href="#workspace">Workspace</a></nav>
    </header>
    <section className="hero" aria-labelledby="page-title">
      <p className="eyebrow">Outcome measurement workspace</p>
      <h1 id="page-title">A clear view of learning outcomes.</h1>
      <p className="lede">The platform foundation is ready. Domain workflows will appear here as they become available.</p>
    </section>
    <section id="status" className="status-card" aria-labelledby="status-title">
      <div><p className="eyebrow">Connection</p><h2 id="status-title">API availability</h2></div>
      {health.isPending && <p role="status">Checking the API…</p>}
      {health.data?.status === 'ok' && <p className="state success" role="status">Connected and ready</p>}
      {health.data?.status === 'unavailable' && <p className="state warning" role="alert">The API is unavailable. Try again shortly.</p>}
      {error?.status === 401 && <p className="state warning" role="alert">Your session is not authorized for this workspace.</p>}
      {error && error.status !== 401 && <p className="state warning" role="alert">We could not reach the API. Try again shortly.</p>}
      {health.isError && <button className="secondary" type="button" onClick={() => void health.refetch()}>Retry connection</button>}
    </section>
    <section id="workspace" className="workspace" aria-labelledby="workspace-title">
      <p className="eyebrow">Next step</p><h2 id="workspace-title">Your workspace is waiting.</h2>
      <p>Navigation and domain screens will be added in the next slices.</p>
    </section>
  </main>;
}
