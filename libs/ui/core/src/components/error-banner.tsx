import * as React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './button';

export interface ErrorBannerProps extends React.ComponentProps<'div'> {
  title?: string;
  message: string;
  detail?: string;
  onRetry?: () => void;
  retryLabel?: string;
  action?: React.ReactNode;
}

export function ErrorBanner({
  title,
  message,
  detail,
  onRetry,
  retryLabel = 'Try again',
  action,
  className,
  ...props
}: ErrorBannerProps) {
  return (
    <div
      role="alert"
      data-slot="error-banner"
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 rounded-[var(--radius-card,10px)] border border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-fg)]',
        className,
      )}
      {...props}
    >
      <div className="flex min-w-0 flex-1 items-start gap-2.5">
        <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div className="min-w-0 space-y-0.5">
          {title && <p className="font-semibold leading-5">{title}</p>}
          <p className="leading-5">{message}</p>
          {detail && (
            <p className="font-mono text-xs opacity-90 [font-variant-numeric:tabular-nums_slashed-zero]">
              {detail}
            </p>
          )}
        </div>
      </div>
      {action ? (
        <div className="shrink-0">{action}</div>
      ) : (
        onRetry && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="shrink-0 border-[var(--status-danger-border)] bg-transparent text-[var(--status-danger-fg)] hover:bg-[var(--status-danger-border)]/25"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {retryLabel}
          </Button>
        )
      )}
    </div>
  );
}
