import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import * as React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import {
  AbsentTag,
  Button,
  Card,
  DialogContent,
  EmptyState,
  ErrorBanner,
  ExemptTag,
  Input,
  MeasuredZeroTag,
  NotAssessedText,
  SkeletonCard,
  SkeletonMetric,
  SkeletonTable,
  SkeletonText,
  StaleTag,
  StatusDot,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  THEME_COLORS,
  ThemeProvider,
  ThemeToggle,
  WithdrawnTag,
  applyThemeToDocument,
  isThemePreference,
  resolveTheme,
} from '../index';

describe('Theme engine', () => {
  it('validates theme preferences and resolves system fallback', () => {
    expect(isThemePreference('light')).toBe(true);
    expect(isThemePreference('dark')).toBe(true);
    expect(isThemePreference('system')).toBe(true);
    expect(isThemePreference('sepia')).toBe(false);

    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
  });

  it('syncs data-theme, dark class, color-scheme, and theme-color meta', () => {
    const attrs = new Map<string, string>();
    const classes = new Set<string>();
    const style = { colorScheme: '' };
    let metaContent = '';
    const mockMeta = {
      name: '',
      get content() {
        return metaContent;
      },
      set content(value: string) {
        metaContent = value;
      },
    };
    const appended: unknown[] = [];
    const mockDoc = {
      documentElement: {
        setAttribute: (key: string, value: string) => attrs.set(key, value),
        classList: {
          toggle: (name: string, force?: boolean) => {
            if (force) classes.add(name);
            else classes.delete(name);
          },
        },
        style,
      },
      head: {
        appendChild: (node: unknown) => appended.push(node),
      },
      querySelector: () => (appended.length ? mockMeta : null),
      createElement: () => mockMeta,
    } as unknown as Document;

    applyThemeToDocument('dark', mockDoc);
    expect(attrs.get('data-theme')).toBe('dark');
    expect(classes.has('dark')).toBe(true);
    expect(style.colorScheme).toBe('dark');
    expect(metaContent).toBe(THEME_COLORS.dark);

    applyThemeToDocument('light', mockDoc);
    expect(attrs.get('data-theme')).toBe('light');
    expect(classes.has('dark')).toBe(false);
    expect(style.colorScheme).toBe('light');
    expect(metaContent).toBe(THEME_COLORS.light);
  });

  it('renders ThemeToggle inside ThemeProvider with accessible label and Lucide SVG', () => {
    const html = renderToStaticMarkup(
      <ThemeProvider defaultTheme="light">
        <ThemeToggle showLabel />
      </ThemeProvider>,
    );
    expect(html).toContain('aria-label="Switch to dark mode"');
    expect(html).toContain('aria-pressed="false"');
    expect(html).toContain('<svg');
    expect(html).toContain('Dark mode');
  });
});

describe('PRD v2 Status primitives', () => {
  it('renders StatusDot with 6px dot and text label', () => {
    const html = renderToStaticMarkup(
      <StatusDot variant="success" label="Published" />,
    );
    expect(html).toContain('data-slot="status-dot"');
    expect(html).toContain('size-1.5');
    expect(html).toContain('Published');
  });

  it('distinguishes MeasuredZero, Absent, Exempt, Withdrawn, Stale, and NotAssessed without relying on color alone', () => {
    const zeroHtml = renderToStaticMarkup(<MeasuredZeroTag />);
    const absentHtml = renderToStaticMarkup(<AbsentTag />);
    const exemptHtml = renderToStaticMarkup(<ExemptTag />);
    const withdrawnHtml = renderToStaticMarkup(<WithdrawnTag />);
    const staleHtml = renderToStaticMarkup(<StaleTag />);
    const unassessedHtml = renderToStaticMarkup(<NotAssessedText />);

    expect(zeroHtml).toContain('0.0');
    expect(zeroHtml).toContain('border-solid');
    expect(zeroHtml).toContain('tabular-nums_slashed-zero');
    expect(zeroHtml).toContain('<svg');

    expect(absentHtml).toContain('ABSENT');
    expect(absentHtml).toContain('border-solid');
    expect(absentHtml).toContain('<svg');

    expect(exemptHtml).toContain('EXEMPT');
    expect(exemptHtml).toContain('border-dashed');
    expect(exemptHtml).toContain('<svg');

    expect(withdrawnHtml).toContain('WITHDRAWN');
    expect(withdrawnHtml).toContain('border-dotted');
    expect(withdrawnHtml).toContain('<svg');

    expect(staleHtml).toContain('STALE');
    expect(staleHtml).toContain('border-solid');
    expect(staleHtml).toContain('<svg');

    expect(unassessedHtml).toContain('— Not assessed');
  });
});

describe('Data Table, Skeleton, EmptyState, and ErrorBanner primitives', () => {
  it('renders Table with scrollbar-gutter, sticky header, sentence-case headers, and tabular numeric cells', () => {
    const html = renderToStaticMarkup(
      <Table>
        <TableHeader sticky>
          <TableRow>
            <TableHead>Program outcome</TableHead>
            <TableHead numeric>Attainment</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>PO1</TableCell>
            <TableCell numeric>84.2%</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    expect(html).toContain('[scrollbar-gutter:stable]');
    expect(html).toContain('sticky top-0');
    expect(html).not.toContain('uppercase');
    expect(html).toContain('text-right');
    expect(html).toContain('tabular-nums_slashed-zero');
  });

  it('renders layout-matched Skeleton variants with reduced-motion support', () => {
    const textHtml = renderToStaticMarkup(<SkeletonText lines={3} />);
    const tableHtml = renderToStaticMarkup(
      <SkeletonTable rows={3} columns={4} />,
    );
    const cardHtml = renderToStaticMarkup(<SkeletonCard />);
    const metricHtml = renderToStaticMarkup(<SkeletonMetric />);

    expect(textHtml).toContain('motion-reduce:animate-none');
    expect(tableHtml).toContain('data-slot="skeleton-table"');
    expect(cardHtml).toContain('data-slot="skeleton-card"');
    expect(metricHtml).toContain('data-slot="skeleton-metric"');
  });

  it('renders actionable EmptyState and inline ErrorBanner with Lucide SVG icons', () => {
    const emptyHtml = renderToStaticMarkup(
      <EmptyState
        title="No offerings yet"
        description="Create a course offering to start mapping outcomes."
        action={<Button>Create offering</Button>}
      />,
    );
    expect(emptyHtml).toContain('No offerings yet');
    expect(emptyHtml).toContain('Create offering');
    expect(emptyHtml).toContain('<svg');

    const errorHtml = renderToStaticMarkup(
      <ErrorBanner
        title="Weight validation failed"
        message="Row LO2 exceeds 100% total weight."
        detail="Expected 100.0%, received 115.0%"
        onRetry={() => undefined}
      />,
    );
    expect(errorHtml).toContain('role="alert"');
    expect(errorHtml).toContain('Weight validation failed');
    expect(errorHtml).toContain('Expected 100.0%, received 115.0%');
    expect(errorHtml).toContain('Try again');
    expect(errorHtml).toContain('<svg');
  });

  it('enforces varied radii tokens across inputs, buttons, and cards without transition-all', () => {
    const buttonHtml = renderToStaticMarkup(<Button>Save</Button>);
    const inputHtml = renderToStaticMarkup(<Input aria-label="Course code" />);
    const cardHtml = renderToStaticMarkup(<Card>Body</Card>);

    expect(buttonHtml).toContain('--radius-input');
    expect(buttonHtml).not.toContain('transition-all');
    expect(inputHtml).toContain('--radius-input');
    expect(cardHtml).toContain('--radius-card');
    expect(DialogContent).toBeDefined();
  });
});

describe('Institutional Navy & Gold globals.css contract', () => {
  const globalsCssPath = resolve(
    process.cwd(),
    '../../../apps/web/app/globals.css',
  );
  const css = readFileSync(globalsCssPath, 'utf8');

  it('registers Tailwind @source for ui/core and all domain modules', () => {
    expect(css).toContain("@source '../../../libs/ui/core/src';");
    expect(css).toContain("@source '../../../libs/ui/modules/access/src';");
    expect(css).toContain("@source '../../../libs/ui/modules/academic/src';");
    expect(css).toContain("@source '../../../libs/ui/modules/reports/src';");
    expect(css).toContain("@source '../../../libs/ui/modules/system/src';");
  });

  it('uses OKLCH hue 254 navy + hue 78 gold tokens, P3 step-up, and avoids forbidden anti-patterns', () => {
    expect(css).toContain('oklch(97.8% 0.006 254)');
    expect(css).toContain('oklch(14.5% 0.022 254)');
    expect(css).toContain('oklch(74.5% 0.145 78)');
    expect(css).toContain('@media (color-gamut: p3)');
    expect(css).toContain('Plus Jakarta Sans');
    expect(css).toContain('IBM Plex Mono');
    expect(css).not.toMatch(/Arial/i);
    expect(css).not.toMatch(/transition:\s*all/i);
    expect(css).not.toMatch(/text-transform:\s*uppercase/i);
  });
});
