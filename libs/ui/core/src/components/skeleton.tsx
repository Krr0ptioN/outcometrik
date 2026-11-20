import * as React from 'react';
import { cn } from '../lib/utils';

function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn(
        'skeleton-shimmer rounded-[var(--radius-input,6px)] bg-[var(--surface-subtle)] motion-reduce:animate-none',
        className,
      )}
      {...props}
    />
  );
}

export interface SkeletonTextProps extends React.ComponentProps<'div'> {
  lines?: number;
}

function SkeletonText({ lines = 3, className, ...props }: SkeletonTextProps) {
  return (
    <div
      data-slot="skeleton-text"
      role="status"
      aria-label="Loading content"
      className={cn('space-y-2', className)}
      {...props}
    >
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn(
            'h-3.5',
            index === lines - 1 && lines > 1 ? 'w-3/5' : 'w-full',
          )}
        />
      ))}
    </div>
  );
}

export interface SkeletonTableProps extends React.ComponentProps<'div'> {
  rows?: number;
  columns?: number;
}

function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
  ...props
}: SkeletonTableProps) {
  return (
    <div
      data-slot="skeleton-table"
      role="status"
      aria-label="Loading table"
      className={cn(
        'overflow-hidden rounded-[var(--radius-card,10px)] border border-border bg-card',
        className,
      )}
      {...props}
    >
      <div className="flex h-10 items-center gap-4 border-b border-border bg-[var(--surface-subtle)] px-3.5">
        {Array.from({ length: columns }).map((_, colIndex) => (
          <Skeleton
            key={colIndex}
            className={cn('h-3', colIndex === 0 ? 'w-28' : 'w-20 flex-1')}
          />
        ))}
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="flex h-11 items-center gap-4 px-3.5">
            {Array.from({ length: columns }).map((_, colIndex) => (
              <Skeleton
                key={colIndex}
                className={cn('h-3.5', colIndex === 0 ? 'w-32' : 'w-16 flex-1')}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function SkeletonCard({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton-card"
      role="status"
      aria-label="Loading card"
      className={cn(
        'space-y-4 rounded-[var(--radius-card,10px)] border border-border bg-card p-5 shadow-[var(--shadow-sm)] dark:shadow-none',
        className,
      )}
      {...props}
    >
      <div className="space-y-2">
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="h-3 w-3/5" />
      </div>
      <SkeletonText lines={3} />
    </div>
  );
}

function SkeletonMetric({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="skeleton-metric"
      role="status"
      aria-label="Loading metric"
      className={cn(
        'space-y-3 rounded-[var(--radius-card,10px)] border border-border bg-card p-4 shadow-[var(--shadow-sm)] dark:shadow-none',
        className,
      )}
      {...props}
    >
      <Skeleton className="h-3 w-28" />
      <div className="flex items-end justify-between gap-3">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-8 w-20" />
      </div>
      <Skeleton className="h-3 w-36" />
    </div>
  );
}

export { Skeleton, SkeletonText, SkeletonTable, SkeletonCard, SkeletonMetric };
