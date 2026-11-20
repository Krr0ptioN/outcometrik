'use client';

import * as React from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'outcometrik-theme';

export const THEME_COLORS: Record<ResolvedTheme, string> = {
  light: '#f6f8fb',
  dark: '#0a111d',
};

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

export function resolveTheme(
  preference: ThemePreference,
  prefersDark: boolean,
): ResolvedTheme {
  if (preference === 'system') {
    return prefersDark ? 'dark' : 'light';
  }
  return preference;
}

export function applyThemeToDocument(
  resolved: ResolvedTheme,
  doc: Document = document,
): void {
  const root = doc.documentElement;
  root.setAttribute('data-theme', resolved);
  root.classList.toggle('dark', resolved === 'dark');
  root.style.colorScheme = resolved;

  let meta = doc.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (!meta) {
    meta = doc.createElement('meta');
    meta.name = 'theme-color';
    doc.head.appendChild(meta);
  }
  meta.content = THEME_COLORS[resolved];
}

export interface ThemeContextValue {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (next: ThemePreference) => void;
  toggleTheme: () => void;
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null);

export interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: ThemePreference;
  storageKey?: string;
}

function readStoredTheme(
  storageKey: string,
  fallback: ThemePreference,
): ThemePreference {
  if (typeof window === 'undefined') {
    return fallback;
  }
  try {
    const stored = window.localStorage.getItem(storageKey);
    return isThemePreference(stored) ? stored : fallback;
  } catch {
    return fallback;
  }
}

function getSystemPrefersDark(): boolean {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return false;
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = THEME_STORAGE_KEY,
}: ThemeProviderProps) {
  const [theme, setThemeState] = React.useState<ThemePreference>(defaultTheme);
  const [systemPrefersDark, setSystemPrefersDark] =
    React.useState<boolean>(false);
  const [hydrated, setHydrated] = React.useState(false);

  React.useEffect(() => {
    setThemeState(readStoredTheme(storageKey, defaultTheme));
    setSystemPrefersDark(getSystemPrefersDark());
    setHydrated(true);

    if (typeof window.matchMedia !== 'function') {
      return;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event: MediaQueryListEvent) => {
      setSystemPrefersDark(event.matches);
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [defaultTheme, storageKey]);

  const resolvedTheme = resolveTheme(theme, systemPrefersDark);

  React.useEffect(() => {
    if (!hydrated) {
      return;
    }
    applyThemeToDocument(resolvedTheme);
  }, [hydrated, resolvedTheme]);

  const setTheme = React.useCallback(
    (next: ThemePreference) => {
      setThemeState(next);
      try {
        window.localStorage.setItem(storageKey, next);
      } catch {
        // Ignore storage write errors in restricted browsing contexts.
      }
      applyThemeToDocument(resolveTheme(next, getSystemPrefersDark()));
    },
    [storageKey],
  );

  const toggleTheme = React.useCallback(() => {
    const next: ResolvedTheme = resolvedTheme === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }, [resolvedTheme, setTheme]);

  const value = React.useMemo<ThemeContextValue>(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
      toggleTheme,
    }),
    [theme, resolvedTheme, setTheme, toggleTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const context = React.useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider.');
  }
  return context;
}
