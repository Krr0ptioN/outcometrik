'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { ThemeProvider, ThemeToggle, TooltipProvider } from '@outcometrik/ui';

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
      }),
  );

  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <TooltipProvider>
          {children}
          <div className="fixed right-4 bottom-4 z-40">
            <ThemeToggle
              showLabel
              className="bg-card/95 backdrop-blur-xs shadow-[var(--shadow-sm)] dark:bg-card/95 dark:shadow-none"
            />
          </div>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
