import * as React from 'react';
import {
  AlertTriangle,
  CircleDot,
  CircleSlash,
  Clock,
  UserMinus,
} from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../lib/utils';

const statusDotVariants = cva('size-1.5 shrink-0 rounded-full', {
  variants: {
    variant: {
      success: 'bg-[var(--status-success-fg)]',
      warning: 'bg-[var(--status-warn-fg)]',
      danger: 'bg-[var(--status-danger-fg)]',
      info: 'bg-[var(--status-info-fg)]',
      neutral: 'bg-muted-foreground',
    },
  },
  defaultVariants: {
    variant: 'neutral',
  },
});

export interface StatusDotProps
  extends React.ComponentProps<'span'>,
    VariantProps<typeof statusDotVariants> {
  label: string;
}

export function StatusDot({
  label,
  variant = 'neutral',
  className,
  ...props
}: StatusDotProps) {
  return (
    <span
      data-slot="status-dot"
      data-variant={variant}
      className={cn(
        'inline-flex items-center gap-1.5 text-[12.5px] font-medium whitespace-nowrap text-muted-foreground',
        className,
      )}
      {...props}
    >
      <span className={statusDotVariants({ variant })} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

const prdStateTagBase =
  'inline-flex items-center gap-1 rounded-[var(--radius-tag,4px)] px-1.5 py-0.5 text-[11.5px] leading-4 font-semibold whitespace-nowrap select-none';

export interface MeasuredZeroTagProps extends React.ComponentProps<'span'> {
  value?: string;
}

/**
 * Explicit numeric measured zero (`0.0`).
 * Distinct solid high-contrast border + icon + slashed-zero mono text
 * so measured zero is never confused with ABSENT, EXEMPT, or unassessed.
 */
export function MeasuredZeroTag({
  value = '0.0',
  className,
  ...props
}: MeasuredZeroTagProps) {
  return (
    <span
      data-slot="state-tag"
      data-state-kind="measured-zero"
      aria-label={`Measured score ${value}`}
      className={cn(
        prdStateTagBase,
        'border-[1.5px] border-solid border-foreground bg-card font-mono text-foreground [font-variant-numeric:tabular-nums_slashed-zero]',
        className,
      )}
      {...props}
    >
      <CircleDot className="size-3 shrink-0" aria-hidden="true" />
      <span>{value}</span>
    </span>
  );
}

export interface StateTagProps extends React.ComponentProps<'span'> {
  label?: string;
}

/**
 * Blocking missing grade (`ABSENT`).
 * Danger palette + warning triangle icon + solid border.
 */
export function AbsentTag({
  label = 'ABSENT',
  className,
  ...props
}: StateTagProps) {
  return (
    <span
      data-slot="state-tag"
      data-state-kind="absent"
      className={cn(
        prdStateTagBase,
        'border border-solid border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-fg)]',
        className,
      )}
      {...props}
    >
      <AlertTriangle className="size-3 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/**
 * Exempt student or assessment (`EXEMPT`, removed from denominator).
 * Info palette + slash icon + dashed border (distinguishable in grayscale).
 */
export function ExemptTag({
  label = 'EXEMPT',
  className,
  ...props
}: StateTagProps) {
  return (
    <span
      data-slot="state-tag"
      data-state-kind="exempt"
      className={cn(
        prdStateTagBase,
        'border border-dashed border-[var(--status-info-border)] bg-[var(--status-info-bg)] text-[var(--status-info-fg)]',
        className,
      )}
      {...props}
    >
      <CircleSlash className="size-3 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/**
 * Withdrawn enrollment (`WITHDRAWN`).
 * Neutral subtle surface + user-minus icon + dotted border.
 */
export function WithdrawnTag({
  label = 'WITHDRAWN',
  className,
  ...props
}: StateTagProps) {
  return (
    <span
      data-slot="state-tag"
      data-state-kind="withdrawn"
      className={cn(
        prdStateTagBase,
        'border border-dotted border-[var(--border-strong)] bg-muted text-muted-foreground',
        className,
      )}
      {...props}
    >
      <UserMinus className="size-3 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

/**
 * Stale calculation or snapshot requiring recomputation (`STALE`).
 * Warning palette + clock icon + solid border.
 */
export function StaleTag({
  label = 'STALE',
  className,
  ...props
}: StateTagProps) {
  return (
    <span
      data-slot="state-tag"
      data-state-kind="stale"
      className={cn(
        prdStateTagBase,
        'border border-solid border-[var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-fg)]',
        className,
      )}
      {...props}
    >
      <Clock className="size-3 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export interface NotAssessedTextProps extends React.ComponentProps<'span'> {
  label?: string;
}

/**
 * Unassessed PO or metric (`— Not assessed`).
 * Never rendered as a zero-height bar or numeric zero.
 */
export function NotAssessedText({
  label = '— Not assessed',
  className,
  ...props
}: NotAssessedTextProps) {
  return (
    <span
      data-slot="not-assessed-text"
      className={cn('text-xs font-normal text-muted-foreground', className)}
      {...props}
    >
      {label}
    </span>
  );
}
