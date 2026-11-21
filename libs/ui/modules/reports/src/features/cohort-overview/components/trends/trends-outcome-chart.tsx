'use client';

import { memo, useId, useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Badge,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  NativeSelect,
  NativeSelectOption,
  NotAssessedText,
  type ChartConfig,
} from '@outcometrik/ui';
import type { CohortTrendPoint } from '../../types';
import { parseNumericScore } from '../cohort-formatters';
import { useTrendsStore } from './trends-store-context';

const TREND_CHART_CONFIG = {
  mean: {
    label: 'Cohort mean',
    color: 'var(--accent-primary)',
  },
} satisfies ChartConfig;

export interface TrendsOutcomeChartProps {
  poSetVersion: number;
  points: CohortTrendPoint[];
}

/**
 * Interactive PO outcome selector + shadcn Recharts AreaChart.
 * Subscribes only to `selectedTrendPoCode` in `TrendsStore` so changing the
 * plotted PO never re-renders the snapshot picker or comparison table.
 */
export const TrendsOutcomeChart = memo(function TrendsOutcomeChart({
  poSetVersion,
  points,
}: TrendsOutcomeChartProps) {
  const trendPoSelectId = useId();
  const gradientId = useId();
  const selectedTrendPoCode = useTrendsStore((s) => s.selectedTrendPoCode);
  const setSelectedPoCode = useTrendsStore((s) => s.setSelectedPoCode);

  const availablePoCodes = useMemo(() => {
    const firstPoint = points[0];
    if (!firstPoint) return [];
    return firstPoint.outcomes.map((o) => ({ code: o.code, label: o.label }));
  }, [points]);

  const activePoCode =
    selectedTrendPoCode &&
    availablePoCodes.some((o) => o.code === selectedTrendPoCode)
      ? selectedTrendPoCode
      : (availablePoCodes[0]?.code ?? '');

  const chartData = useMemo(
    () =>
      points.map((point) => {
        const match = point.outcomes.find((o) => o.code === activePoCode);
        const val = match && match.n > 0 ? parseNumericScore(match.mean) : null;
        return {
          id: point.publication_id,
          label: point.term?.label ?? `Series v${point.series_version}`,
          mean: val,
          rawMean: match?.mean ?? '—',
        };
      }),
    [points, activePoCode],
  );

  const hasValidPoints = chartData.some((pt) => pt.mean !== null);

  return (
    <div className="space-y-4">
      {availablePoCodes.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <label
              htmlFor={trendPoSelectId}
              className="text-xs font-medium text-muted-foreground"
            >
              Chart outcome
            </label>
            <NativeSelect
              id={trendPoSelectId}
              value={activePoCode}
              onChange={(e) => setSelectedPoCode(e.target.value)}
              className="h-8 w-56 bg-card text-xs"
            >
              {availablePoCodes.map((po) => (
                <NativeSelectOption key={po.code} value={po.code}>
                  {po.code} · {po.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <Badge variant="secondary" className="tabular-mono">
            PO-Set v{poSetVersion} · {points.length} snapshot
            {points.length === 1 ? '' : 's'}
          </Badge>
        </div>
      )}

      {activePoCode && points.length > 0 && (
        <div className="rounded-[var(--radius-card,10px)] border border-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h4 className="text-sm font-semibold text-foreground">
                {activePoCode} attainment trend (0–100 scale)
              </h4>
              <p className="text-xs text-muted-foreground">
                Chronological mean across compatible PO-Set snapshots. Dashed
                rule marks 70.0 target threshold.
              </p>
            </div>
          </div>

          {!hasValidPoints ? (
            <div className="flex h-36 items-center justify-center rounded-md border border-dashed bg-muted/30">
              <NotAssessedText label="— Not assessed across selected snapshots" />
            </div>
          ) : (
            <>
              <ChartContainer config={TREND_CHART_CONFIG} className="h-56 w-full">
                <AreaChart
                  accessibilityLayer
                  data={chartData}
                  margin={{ left: 0, right: 16, top: 12, bottom: 4 }}
                >
                  <defs>
                    <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="var(--color-mean)"
                        stopOpacity={0.18}
                      />
                      <stop
                        offset="95%"
                        stopColor="var(--color-mean)"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    vertical={false}
                    stroke="var(--border-hairline)"
                    strokeDasharray="3 3"
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                  />
                  <YAxis
                    domain={[0, 100]}
                    ticks={[0, 25, 50, 70, 85, 100]}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <ReferenceLine
                    y={70}
                    stroke="var(--accent-primary)"
                    strokeOpacity={0.45}
                    strokeDasharray="4 4"
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<ChartTooltipContent indicator="line" />}
                  />
                  <Area
                    dataKey="mean"
                    type="monotone"
                    fill={`url(#${gradientId})`}
                    stroke="var(--color-mean)"
                    strokeWidth={2.25}
                    dot={{
                      r: 4,
                      fill: 'var(--surface-raised)',
                      stroke: 'var(--color-mean)',
                      strokeWidth: 2,
                    }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                </AreaChart>
              </ChartContainer>
              <svg
                aria-hidden="true"
                className="sr-only"
                width="1"
                height="1"
              />
              <ul className="sr-only">
                {chartData.map((pt) => (
                  <li key={pt.id}>
                    {pt.label}: {pt.rawMean}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
});
