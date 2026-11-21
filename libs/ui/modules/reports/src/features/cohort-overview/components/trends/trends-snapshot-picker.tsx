'use client';

import { memo } from 'react';
import { Badge, Button, StaleTag } from '@outcometrik/ui';
import { useTrendsStore } from './trends-store-context';
import { useTrendsSelection } from './use-trends-selection';

/**
 * Snapshot checkbox selector for chronological trend comparisons.
 * Subscribes only to snapshot selection slices in `TrendsStore` so changing
 * the chart's PO outcome dropdown never re-renders this picker.
 */
export const TrendsSnapshotPicker = memo(function TrendsSnapshotPicker() {
  const {
    publications,
    activePoSetVersion,
    compatibleIds,
    selectedIdSet,
    isCustomSelection,
    hasIncompatibleSelection,
  } = useTrendsSelection();

  const togglePublication = useTrendsStore((s) => s.togglePublication);
  const resetPublications = useTrendsStore((s) => s.resetPublications);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3
            id="po-trends-title"
            className="text-base font-semibold tracking-tight"
          >
            Compatible PO-set trend comparison
          </h3>
          <p className="text-xs text-muted-foreground">
            Only publications sharing the same PO-set version can be compared
            chronologically. Including a snapshot from a different PO-set
            triggers the server compatibility guard.
          </p>
        </div>
        {isCustomSelection && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={resetPublications}
            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Reset to compatible PO-Set v{activePoSetVersion ?? '?'}
          </Button>
        )}
      </div>

      {publications.length > 0 && (
        <fieldset className="space-y-2 rounded-[var(--radius-card,10px)] border border-border/80 bg-[var(--surface-subtle)]/40 p-3.5">
          <legend className="px-1 text-xs font-medium text-muted-foreground">
            Snapshots included in comparison
          </legend>
          <div className="flex flex-wrap gap-2">
            {publications.map((pub) => {
              const checked = selectedIdSet.has(pub.id);
              const isDifferentSet =
                activePoSetVersion !== undefined &&
                pub.po_set_version !== activePoSetVersion;
              return (
                <label
                  key={pub.id}
                  className={`inline-flex cursor-pointer items-center gap-2 rounded-[var(--radius-input,6px)] border px-2.5 py-1.5 text-xs transition-colors duration-150 ${
                    checked
                      ? 'border-[var(--accent-border)] bg-[var(--accent-soft)] text-foreground'
                      : 'border-border bg-card text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => togglePublication(pub.id, compatibleIds)}
                    className="accent-[var(--accent-primary)]"
                  />
                  <span className="tabular-mono font-medium">
                    Series v{pub.series_version}
                  </span>
                  <Badge
                    variant={isDifferentSet ? 'outline' : 'secondary'}
                    className="tabular-mono px-1.5 py-0 text-[11px]"
                  >
                    PO-Set v{pub.po_set_version}
                  </Badge>
                  {pub.stale && <StaleTag label="STALE" />}
                </label>
              );
            })}
          </div>
          {hasIncompatibleSelection && (
            <p className="text-xs text-[var(--status-warn-fg)]">
              Selected snapshots span multiple PO-Set versions; requesting
              comparison will be rejected by the server compatibility guard.
            </p>
          )}
        </fieldset>
      )}
    </div>
  );
});
