import * as React from 'react';
import { cn } from '../lib/utils';

export interface BrandCrestProps {
  href?: string;
  subtitle?: string;
  collapsed?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export function BrandCrest({
  href = '/',
  subtitle,
  collapsed = false,
  className,
  size = 'md',
}: BrandCrestProps) {
  const iconBoxSize = size === 'sm' ? 'size-7' : 'size-8';
  const svgSize = size === 'sm' ? 15 : 16;

  return (
    <a
      href={href}
      aria-label="Outcometrik home"
      data-slot="brand-crest"
      className={cn(
        'group inline-flex min-w-0 items-center gap-2.5 rounded-[var(--radius-input)] text-foreground no-underline transition-opacity duration-150 ease-out hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 motion-reduce:transition-none',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-[var(--radius-input)] bg-[var(--brand-mark-bg)] text-[var(--brand-mark-fg)] shadow-xs',
          iconBoxSize,
        )}
      >
        <svg
          width={svgSize}
          height={svgSize}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 3 3 7.5 12 12l9-4.5L12 3Z" />
          <path d="M6 10.2v5.3c0 1.7 2.7 3 6 3s6-1.3 6-3v-5.3" />
          <path d="M21 7.5v6.5" />
        </svg>
      </span>
      {!collapsed && (
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-foreground">
            Outcometrik
          </span>
          {subtitle ? (
            <span className="truncate text-[11.5px] font-normal text-muted-foreground">
              {subtitle}
            </span>
          ) : null}
        </span>
      )}
    </a>
  );
}
