import { shortRef } from '../api';
import type {
  CohortDistribution,
  CohortExclusions,
  CohortOutcomeMetric,
  CoordinatorPublication,
} from '../types';

/**
 * Single-hue Institutional Navy opacity ramp for the 4 attainment bands:
 * 85-100 = 100% navy, 70-84.9 = 62% navy, 50-69.9 = 32% navy, <50 = danger.
 */
export const BUCKET_META: ReadonlyArray<{
  key: keyof CohortDistribution;
  label: string;
  barClass: string;
  swatchClass: string;
}> = [
  {
    key: '<50',
    label: '<50',
    barClass: 'bg-[var(--status-danger-fg)]',
    swatchClass: 'bg-[var(--status-danger-fg)]',
  },
  {
    key: '50-69.9',
    label: '50–69.9',
    barClass: 'bg-[color-mix(in_oklch,var(--accent-primary)_32%,transparent)]',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_32%,transparent)]',
  },
  {
    key: '70-84.9',
    label: '70–84.9',
    barClass: 'bg-[color-mix(in_oklch,var(--accent-primary)_62%,transparent)]',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_62%,transparent)]',
  },
  {
    key: '85-100',
    label: '85–100',
    barClass: 'bg-[var(--accent-primary)]',
    swatchClass: 'bg-[var(--accent-primary)]',
  },
];

export function formatExclusionParts(exclusions: CohortExclusions): string[] {
  const parts: string[] = [];
  if (exclusions.NOT_ASSESSED > 0) {
    parts.push(`Not assessed: ${exclusions.NOT_ASSESSED}`);
  }
  if (exclusions.INCOMPLETE > 0) {
    parts.push(`Incomplete: ${exclusions.INCOMPLETE}`);
  }
  if (exclusions.ALL_EXEMPT > 0) {
    parts.push(`Exempt: ${exclusions.ALL_EXEMPT}`);
  }
  if (exclusions.UNMAPPED > 0) {
    parts.push(`Unmapped: ${exclusions.UNMAPPED}`);
  }
  return parts;
}

export function totalExclusionsCount(exclusions: CohortExclusions): number {
  return (
    exclusions.NOT_ASSESSED +
    exclusions.INCOMPLETE +
    exclusions.ALL_EXEMPT +
    exclusions.UNMAPPED
  );
}

export function formatPublicationLabel(pub: CoordinatorPublication): string {
  const datePart = pub.published_at ? pub.published_at.slice(0, 10) : 'Draft';
  const statusPart = pub.stale ? 'Stale' : 'Published';
  return `Series v${pub.series_version} · PO-Set v${pub.po_set_version} · ${datePart} (${statusPart}) · ${shortRef(pub.id)}`;
}

export function formatMinMax(outcome: CohortOutcomeMetric): string {
  if (outcome.n === 0 || outcome.min === null || outcome.max === null) {
    return '—';
  }
  return `${outcome.min}–${outcome.max}`;
}

export function isMeasuredZero(outcome: CohortOutcomeMetric): boolean {
  if (outcome.n === 0 || outcome.mean === null) return false;
  const parsed = Number(outcome.mean);
  return Number.isFinite(parsed) && parsed === 0;
}

export function parseNumericScore(value: string | null): number | null {
  if (value === null) return null;
  const num = Number(value);
  return Number.isFinite(num) ? Math.max(0, Math.min(100, num)) : null;
}
