'use client';

import * as React from 'react';
import { Moon, Sun } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './button';
import { useTheme } from './theme-provider';

export interface ThemeToggleProps
  extends Omit<React.ComponentProps<typeof Button>, 'onClick'> {
  showLabel?: boolean;
}

export function ThemeToggle({
  className,
  showLabel = false,
  variant = 'outline',
  size,
  ...props
}: ThemeToggleProps) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const actionLabel = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <Button
      type="button"
      variant={variant}
      size={size ?? (showLabel ? 'sm' : 'icon-sm')}
      onClick={toggleTheme}
      aria-label={actionLabel}
      aria-pressed={isDark}
      title={actionLabel}
      data-slot="theme-toggle"
      data-theme-state={resolvedTheme}
      className={cn(
        'transition-[background-color,border-color,color] duration-150 ease-out motion-reduce:transition-none',
        className,
      )}
      {...props}
    >
      {isDark ? (
        <Sun className="size-4" aria-hidden="true" />
      ) : (
        <Moon className="size-4" aria-hidden="true" />
      )}
      {showLabel ? (
        <span>{isDark ? 'Light mode' : 'Dark mode'}</span>
      ) : (
        <span className="sr-only">{actionLabel}</span>
      )}
    </Button>
  );
}
