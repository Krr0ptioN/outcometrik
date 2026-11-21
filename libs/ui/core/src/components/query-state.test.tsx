import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { QueryState, createQueryState } from './query-state';

describe('QueryState & createQueryState', () => {
  const DomainQuery = createQueryState({
    formatError: (err) => `Formatted: ${String(err)}`,
  });

  it('renders Loading slot when query is pending', () => {
    const markup = renderToStaticMarkup(
      <DomainQuery
        query={{ data: undefined, isPending: true, isError: false, error: null }}
      >
        <DomainQuery.Loading label="Fetching metrics…" />
        <DomainQuery.Error title="Failed" />
        <DomainQuery.Ready>{() => 'Ready body'}</DomainQuery.Ready>
      </DomainQuery>,
    );

    expect(markup).toContain('Fetching metrics…');
    expect(markup).toContain('role="status"');
    expect(markup).not.toContain('Ready body');
    expect(markup).not.toContain('Failed');
  });

  it('renders Error slot with factory-bound formatter on error', () => {
    const markup = renderToStaticMarkup(
      <DomainQuery
        query={{
          data: undefined,
          isPending: false,
          isError: true,
          error: 'scope_denied',
        }}
      >
        <DomainQuery.Error title="Access blocked" />
        <DomainQuery.Ready>{() => 'Ready body'}</DomainQuery.Ready>
      </DomainQuery>,
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain('Access blocked');
    expect(markup).toContain('Formatted: scope_denied');
    expect(markup).not.toContain('Ready body');
  });

  it('renders Empty slot when isEmpty or treatErrorAsEmpty matches', () => {
    const emptyListMarkup = renderToStaticMarkup(
      <QueryState<string[]>
        query={{ data: [], isPending: false, isError: false, error: null }}
        isEmpty={(rows) => rows.length === 0}
      >
        <QueryState.Empty>No items found</QueryState.Empty>
        <QueryState.Ready>
          {(rows: string[]) => rows.join(',')}
        </QueryState.Ready>
      </QueryState>,
    );
    expect(emptyListMarkup).toContain('No items found');

    const notFoundEmptyMarkup = renderToStaticMarkup(
      <DomainQuery
        query={{
          data: undefined,
          isPending: false,
          isError: true,
          error: { status: 404 },
        }}
        treatErrorAsEmpty={(err) =>
          typeof err === 'object' &&
          err !== null &&
          'status' in err &&
          (err as { status: number }).status === 404
        }
      >
        <DomainQuery.Error title="Should not show" />
        <DomainQuery.Empty>404 treated as empty</DomainQuery.Empty>
      </DomainQuery>,
    );
    expect(notFoundEmptyMarkup).toContain('404 treated as empty');
    expect(notFoundEmptyMarkup).not.toContain('Should not show');
  });

  it('renders Ready slot with narrowed data when loaded', () => {
    const markup = renderToStaticMarkup(
      <DomainQuery<{ count: number }>
        query={{
          data: { count: 42 },
          isPending: false,
          isError: false,
          error: null,
        }}
      >
        <DomainQuery.Loading />
        <DomainQuery.Ready>
          {(data: { count: number }) => `Count: ${data.count}`}
        </DomainQuery.Ready>
      </DomainQuery>,
    );

    expect(markup).toContain('Count: 42');
  });
});
