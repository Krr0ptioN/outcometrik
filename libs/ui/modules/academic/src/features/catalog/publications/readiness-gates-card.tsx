'use client';

import { memo } from 'react';
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  StatusDot,
} from '@outcometrik/ui';
import type { ProgramOutcomeSet } from '../../syllabus/api';
import type { CalculationRun } from '../publications-api';

export interface ReadinessGatesCardProps {
  activePoSet: ProgramOutcomeSet | null;
  totalOfferings: number;
  approvedOfferings: number;
  draftOnlyOfferings: number;
  latestRun: CalculationRun | null;
}

export const ReadinessGatesCard = memo(function ReadinessGatesCard({
  activePoSet,
  totalOfferings,
  approvedOfferings,
  draftOnlyOfferings,
  latestRun,
}: ReadinessGatesCardProps) {
  const hasActivePoSet = Boolean(activePoSet);
  const hasApprovedSyllabus = approvedOfferings > 0;
  const latestRunIncomplete =
    latestRun !== null && !latestRun.is_complete_for_publication;

  return (
    <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle>
          <h2 className="text-base font-semibold tracking-tight">
            Pre-publication readiness gates
          </h2>
        </CardTitle>
        <CardDescription>
          Authoritative prerequisites verified before sealing an immutable
          publication series.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-5">
        <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
          <div className="flex items-start gap-2.5">
            {hasActivePoSet ? (
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                aria-hidden="true"
              />
            ) : (
              <ShieldAlert
                className="mt-0.5 size-4 shrink-0 text-[var(--status-danger-fg)]"
                aria-hidden="true"
              />
            )}
            <div>
              <p className="text-sm font-medium">Active PO1–PO11 set</p>
              <p className="text-xs text-muted-foreground">
                {activePoSet
                  ? `PO-Set v${activePoSet.version} active (effective ${activePoSet.effective_date ?? 'set'}).`
                  : 'No active PO set found. Activate a PO set first.'}
              </p>
            </div>
          </div>
          <StatusDot
            variant={hasActivePoSet ? 'success' : 'danger'}
            label={hasActivePoSet ? 'Ready' : 'Blocked'}
          />
        </div>

        <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
          <div className="flex items-start gap-2.5">
            {hasApprovedSyllabus ? (
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                aria-hidden="true"
              />
            ) : (
              <ShieldAlert
                className="mt-0.5 size-4 shrink-0 text-[var(--status-danger-fg)]"
                aria-hidden="true"
              />
            )}
            <div>
              <p className="text-sm font-medium">Approved syllabi</p>
              <p className="text-xs text-muted-foreground">
                {approvedOfferings} of {totalOfferings} offerings have an
                approved locked syllabus.
                {draftOnlyOfferings > 0
                  ? ` ${draftOnlyOfferings} offering(s) still have unapproved drafts.`
                  : ''}
              </p>
            </div>
          </div>
          <StatusDot
            variant={
              hasApprovedSyllabus
                ? draftOnlyOfferings > 0
                  ? 'warning'
                  : 'success'
                : 'danger'
            }
            label={
              hasApprovedSyllabus
                ? draftOnlyOfferings > 0
                  ? 'Partial'
                  : 'Ready'
                : 'Blocked'
            }
          />
        </div>

        <div className="flex items-start justify-between gap-3 rounded-[var(--radius-input,6px)] border border-border p-3">
          <div className="flex items-start gap-2.5">
            {latestRun === null || latestRunIncomplete ? (
              <AlertTriangle
                className="mt-0.5 size-4 shrink-0 text-[var(--status-warn-fg)]"
                aria-hidden="true"
              />
            ) : (
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-[var(--status-success-fg)]"
                aria-hidden="true"
              />
            )}
            <div>
              <p className="text-sm font-medium">
                Released grades &amp; blocking absents
              </p>
              <p className="text-xs text-muted-foreground">
                {latestRun === null
                  ? 'No program calculation run yet. Running calculation validates released grades and blocking ABSENT states.'
                  : latestRunIncomplete
                    ? 'Latest run flagged incomplete grades or blocking ABSENT records. Unmeasured students will be excluded (never coerced to zero).'
                    : `Latest run ${latestRun.id.slice(0, 8)} is complete for publication (policy ${latestRun.policy_version}).`}
              </p>
            </div>
          </div>
          <StatusDot
            variant={
              latestRun === null
                ? 'neutral'
                : latestRunIncomplete
                  ? 'warning'
                  : 'success'
            }
            label={
              latestRun === null
                ? 'Pending run'
                : latestRunIncomplete
                  ? 'Absents warning'
                  : 'Complete'
            }
          />
        </div>
      </CardContent>
    </Card>
  );
});
