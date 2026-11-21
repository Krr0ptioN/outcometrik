'use client';

import * as React from 'react';
import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from 'react';
import { Alert, AlertDescription, AlertTitle } from './alert';
import { Skeleton } from './skeleton';

/**
 * Structural adapter for TanStack Query results (or any async query shape).
 * Keeps `@outcometrik/ui` decoupled from `@tanstack/react-query`.
 */
export interface QueryLike<T> {
  data: T | undefined;
  isPending: boolean;
  isError: boolean;
  error: unknown;
}

export type QueryPhase = 'loading' | 'error' | 'empty' | 'ready';

interface QueryStateContextValue<T> {
  phase: QueryPhase;
  data: T | undefined;
  error: unknown;
  formatError: (error: unknown) => string;
}

const QueryStateContext = createContext<QueryStateContextValue<unknown> | null>(
  null,
);

function useQueryStateContext<T>(slotName: string): QueryStateContextValue<T> {
  const ctx = useContext(QueryStateContext);
  if (!ctx) {
    throw new Error(
      `<QueryState.${slotName}> must be rendered inside <QueryState>.`,
    );
  }
  return ctx as QueryStateContextValue<T>;
}

function defaultFormatError(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return 'Unable to load the requested records. Refresh the page or retry the request.';
}

export interface QueryStateRootProps<T> {
  query: QueryLike<T>;
  /** Optional override when data is already supplied synchronously (e.g. via props). */
  fallbackData?: T;
  /** Strategy: decide whether loaded data counts as empty. */
  isEmpty?: (data: T) => boolean;
  /** Strategy: treat specific errors (e.g. HTTP 404) as empty state instead of error. */
  treatErrorAsEmpty?: (error: unknown) => boolean;
  /** Strategy: format an unknown error into safe user-facing text. */
  formatError?: (error: unknown) => string;
  children: ReactNode;
}

function QueryStateRoot<T>({
  query,
  fallbackData,
  isEmpty,
  treatErrorAsEmpty,
  formatError = defaultFormatError,
  children,
}: QueryStateRootProps<T>) {
  const resolvedData = fallbackData !== undefined ? fallbackData : query.data;
  const usingFallback = fallbackData !== undefined;

  const phase: QueryPhase = useMemo(() => {
    if (!usingFallback && query.isPending) return 'loading';
    if (!usingFallback && query.isError) {
      return treatErrorAsEmpty?.(query.error) ? 'empty' : 'error';
    }
    if (resolvedData === undefined || isEmpty?.(resolvedData)) return 'empty';
    return 'ready';
  }, [
    usingFallback,
    query.isPending,
    query.isError,
    query.error,
    treatErrorAsEmpty,
    resolvedData,
    isEmpty,
  ]);

  const value = useMemo<QueryStateContextValue<T>>(
    () => ({
      phase,
      data: resolvedData,
      error: query.error,
      formatError,
    }),
    [phase, resolvedData, query.error, formatError],
  );

  return (
    <QueryStateContext.Provider
      value={value as QueryStateContextValue<unknown>}
    >
      {children}
    </QueryStateContext.Provider>
  );
}

export interface QueryStateLoadingProps {
  children?: ReactNode;
  label?: string;
}

function QueryStateLoading({ children, label }: QueryStateLoadingProps) {
  const { phase } = useQueryStateContext('Loading');
  if (phase !== 'loading') return null;
  if (children !== undefined) return <>{children}</>;
  return (
    <div className="space-y-2" role="status">
      {label && <p className="text-sm text-muted-foreground">{label}</p>}
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export interface QueryStateErrorProps {
  title?: string;
  format?: (error: unknown) => string;
  children?: ReactNode | ((error: unknown, message: string) => ReactNode);
}

function QueryStateError({
  title = 'Unable to load data',
  format,
  children,
}: QueryStateErrorProps) {
  const { phase, error, formatError } = useQueryStateContext('Error');
  if (phase !== 'error') return null;
  const message = (format ?? formatError)(error);
  if (typeof children === 'function') {
    return <>{children(error, message)}</>;
  }
  if (children !== undefined) {
    return <>{children}</>;
  }
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

export interface QueryStateEmptyProps {
  children: ReactNode;
}

function QueryStateEmpty({ children }: QueryStateEmptyProps) {
  const { phase } = useQueryStateContext('Empty');
  if (phase !== 'empty') return null;
  return <>{children}</>;
}

export interface QueryStateReadyProps<T> {
  children: ReactNode | ((data: T) => ReactNode);
}

function QueryStateReady<T>({ children }: QueryStateReadyProps<T>) {
  const { phase, data } = useQueryStateContext<T>('Ready');
  if (phase !== 'ready' || data === undefined) return null;
  if (typeof children === 'function') {
    return <>{(children as (value: T) => ReactNode)(data)}</>;
  }
  return <>{children}</>;
}

export const QueryState = Object.assign(QueryStateRoot, {
  Loading: QueryStateLoading,
  Error: QueryStateError,
  Empty: QueryStateEmpty,
  Ready: QueryStateReady,
});

export interface CreateQueryStateOptions {
  formatError: (error: unknown) => string;
}

/**
 * Factory Method: creates a domain-scoped compound QueryState component
 * with the module's error formatter pre-bound so call sites stay terse.
 */
export function createQueryState({ formatError }: CreateQueryStateOptions) {
  function BoundQueryState<T>(
    props: Omit<QueryStateRootProps<T>, 'formatError'> & {
      formatError?: (error: unknown) => string;
    },
  ) {
    return (
      <QueryStateRoot<T>
        {...props}
        formatError={props.formatError ?? formatError}
      />
    );
  }

  return Object.assign(BoundQueryState, {
    Loading: QueryStateLoading,
    Error: QueryStateError,
    Empty: QueryStateEmpty,
    Ready: QueryStateReady,
  });
}
