'use client';

import * as React from 'react';
import { cn } from '../lib/utils';

function Table({ className, ...props }: React.ComponentProps<'table'>) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto [scrollbar-gutter:stable]"
    >
      <table
        data-slot="table"
        className={cn('w-full caption-bottom text-sm', className)}
        {...props}
      />
    </div>
  );
}

function TableHeader({
  className,
  sticky = true,
  ...props
}: React.ComponentProps<'thead'> & { sticky?: boolean }) {
  return (
    <thead
      data-slot="table-header"
      data-sticky={sticky ? 'true' : undefined}
      className={cn(
        'bg-[var(--surface-subtle)] [&_tr]:border-b [&_tr]:border-border',
        sticky && 'sticky top-0 z-10',
        className,
      )}
      {...props}
    />
  );
}

function TableBody({ className, ...props }: React.ComponentProps<'tbody'>) {
  return (
    <tbody
      data-slot="table-body"
      className={cn('[&_tr:last-child]:border-0', className)}
      {...props}
    />
  );
}

function TableFooter({ className, ...props }: React.ComponentProps<'tfoot'>) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        'border-t border-border bg-[var(--surface-subtle)] font-medium [&>tr]:last:border-b-0',
        className,
      )}
      {...props}
    />
  );
}

function TableRow({ className, ...props }: React.ComponentProps<'tr'>) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        'h-11 border-b border-border transition-colors duration-150 ease-out hover:bg-[var(--surface-hover)] has-aria-expanded:bg-[var(--surface-hover)] data-[state=selected]:bg-accent',
        className,
      )}
      {...props}
    />
  );
}

function TableHead({
  className,
  numeric = false,
  ...props
}: React.ComponentProps<'th'> & { numeric?: boolean }) {
  return (
    <th
      data-slot="table-head"
      data-numeric={numeric ? 'true' : undefined}
      className={cn(
        'h-10 px-3.5 text-left align-middle text-[12.5px] font-medium whitespace-nowrap text-[var(--text-secondary)] [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]',
        numeric &&
          'text-right font-mono [font-variant-numeric:tabular-nums_slashed-zero]',
        className,
      )}
      {...props}
    />
  );
}

function TableCell({
  className,
  numeric = false,
  ...props
}: React.ComponentProps<'td'> & { numeric?: boolean }) {
  return (
    <td
      data-slot="table-cell"
      data-numeric={numeric ? 'true' : undefined}
      className={cn(
        'px-3.5 py-2.5 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]',
        numeric &&
          'text-right font-mono [font-variant-numeric:tabular-nums_slashed-zero]',
        className,
      )}
      {...props}
    />
  );
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<'caption'>) {
  return (
    <caption
      data-slot="table-caption"
      className={cn('mt-4 text-sm text-muted-foreground', className)}
      {...props}
    />
  );
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
};
