'use client';

import { useMemo, useState } from 'react';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  MeasuredZeroTag,
  NotAssessedText,
  type ChartConfig,
  type TooltipPayloadItem,
} from '@outcometrik/ui';
import { formatCoveragePercent } from '../api';
import type { CohortDistribution, CohortOutcomeMetric } from '../types';

export const DISTRIBUTION_BANDS: ReadonlyArray<{
  key: keyof CohortDistribution;
  label: string;
  shortLabel: string;
  fill: string;
  textFill: string;
  swatchClass: string;
}> = [
  {
    key: '<50',
    label: '<50',
    shortLabel: '<50',
    fill: 'var(--status-danger-fg)',
    textFill: '#ffffff',
    swatchClass: 'bg-[var(--status-danger-fg)]',
  },
  {
    key: '50-69.9',
    label: '50–69.9',
    shortLabel: '50–69',
    fill: 'color-mix(in oklch, var(--accent-primary) 34%, transparent)',
    textFill: 'var(--text-primary)',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_34%,transparent)]',
  },
  {
    key: '70-84.9',
    label: '70–84.9',
    shortLabel: '70–84',
    fill: 'color-mix(in oklch, var(--accent-primary) 64%, transparent)',
    textFill: 'var(--accent-contrast)',
    swatchClass:
      'bg-[color-mix(in_oklch,var(--accent-primary)_64%,transparent)]',
  },
  {
    key: '85-100',
    label: '85–100',
    shortLabel: '85–100',
    fill: 'var(--accent-primary)',
    textFill: 'var(--accent-contrast)',
    swatchClass: 'bg-[var(--accent-primary)]',
  },
];

const PO_CHART_CONFIG = {
  meanValue: {
    label: 'Mean attainment',
    color: 'var(--accent-primary)',
  },
  below50: {
    label: '<50',
    color: 'var(--status-danger-fg)',
  },
  band50: {
    label: '50–69.9',
    color: 'color-mix(in oklch, var(--accent-primary) 34%, transparent)',
  },
  band70: {
    label: '70–84.9',
    color: 'color-mix(in oklch, var(--accent-primary) 64%, transparent)',
  },
  band85: {
    label: '85–100',
    color: 'var(--accent-primary)',
  },
} satisfies ChartConfig;

interface PoChartDatum {
  code: string;
  label: string;
  displayLabel: string;
  meanValue: number;
  rawMean: string | null;
  n: number;
  populationSize: number;
  coveragePct: string;
  isMeasuredZero: boolean;
  isUnassessed: boolean;
  distribution: CohortDistribution;
  outcome: CohortOutcomeMetric;
}

interface CustomBarShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  background?: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
  };
  payload?: PoChartDatum;
  activeCode: string | null;
  pinnedCode: string | null;
  onHover: (code: string | null) => void;
  onTogglePin: (code: string) => void;
}

const EXPAND_TRANSITION = {
  duration: 0.26,
  ease: [0.22, 1, 0.36, 1] as const,
};

function truncateLabel(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(4, maxChars - 1))}…`;
}

function InteractivePoBarShape({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  background,
  payload,
  activeCode,
  pinnedCode,
  onHover,
  onTogglePin,
}: CustomBarShapeProps) {
  if (!payload || height <= 0) return null;

  const fullWidth = Math.max(background?.width ?? width, width, 1);
  const barRadius = 6;
  const isExpanded =
    !payload.isUnassessed &&
    (activeCode === payload.code || pinnedCode === payload.code);
  const isPinned = pinnedCode === payload.code;

  // Unassessed PO: dashed neutral track + "— Not assessed" (never a zero-height bar)
  if (payload.isUnassessed) {
    return (
      <g
        role="group"
        aria-label={`${payload.code} ${payload.label}: Not assessed (0 of ${payload.populationSize} measured)`}
      >
        <rect
          x={x}
          y={y}
          width={fullWidth}
          height={height}
          rx={barRadius}
          fill="var(--surface-subtle)"
          fillOpacity={0.55}
          stroke="var(--border-strong)"
          strokeDasharray="4 4"
          strokeWidth={1}
        />
        <text
          x={x + 10}
          y={y + height / 2 + 4}
          fill="var(--text-muted)"
          fontSize={12}
          fontWeight={500}
        >
          {truncateLabel(
            `${payload.code} · ${payload.label}`,
            Math.max(18, Math.floor((fullWidth - 110) / 7)),
          )}
        </text>
        <text
          x={x + fullWidth + 10}
          y={y + height / 2 + 4}
          fill="var(--text-muted)"
          fontSize={11.5}
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          — Not assessed
        </text>
      </g>
    );
  }

  // Compute proportional 4-band segments across 100% of fullWidth
  const segments = DISTRIBUTION_BANDS.reduce<
    Array<{
      key: keyof CohortDistribution;
      label: string;
      shortLabel: string;
      count: number;
      pct: number;
      segX: number;
      segWidth: number;
      fill: string;
      textFill: string;
    }>
  >((acc, band) => {
    const count = payload.distribution[band.key];
    if (count <= 0) return acc;
    const prevEnd =
      acc.length > 0
        ? acc[acc.length - 1].segX + acc[acc.length - 1].segWidth
        : x;
    const pct = (count / payload.n) * 100;
    const segWidth = (count / payload.n) * fullWidth;
    acc.push({
      key: band.key,
      label: band.label,
      shortLabel: band.shortLabel,
      count,
      pct,
      segX: prevEnd,
      segWidth,
      fill: band.fill,
      textFill: band.textFill,
    });
    return acc;
  }, []);

  const restingWidth = payload.isMeasuredZero ? 8 : Math.max(width, 6);
  const clipId = `po-bar-clip-${payload.code.replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const labelFitsInsideResting = restingWidth >= 140;
  const maxInsideChars = Math.max(10, Math.floor((restingWidth - 20) / 7));

  return (
    <g
      role="button"
      tabIndex={0}
      aria-pressed={isPinned}
      aria-label={`${payload.code} ${payload.label}: Mean ${payload.rawMean ?? '0.0'}, n = ${payload.n} of ${payload.populationSize} (${payload.coveragePct} coverage). Activate to toggle 4-band distribution.`}
      className="cursor-pointer outline-none"
      onMouseEnter={() => onHover(payload.code)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(payload.code)}
      onBlur={() => onHover(null)}
      onClick={() => onTogglePin(payload.code)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onTogglePin(payload.code);
        } else if (e.key === 'Escape' && isPinned) {
          e.preventDefault();
          onTogglePin(payload.code);
        }
      }}
    >
      <defs>
        <clipPath id={clipId}>
          <motion.rect
            x={x}
            y={y}
            height={height}
            rx={barRadius}
            initial={false}
            animate={{ width: isExpanded ? fullWidth : restingWidth }}
            transition={EXPAND_TRANSITION}
          />
        </clipPath>
      </defs>

      {/* Subtle full-width background track (0–100 scale) */}
      <rect
        x={x}
        y={y}
        width={fullWidth}
        height={height}
        rx={barRadius}
        fill="var(--surface-subtle)"
        fillOpacity={isExpanded ? 0.9 : 0.65}
        stroke={isPinned ? 'var(--accent-primary)' : 'transparent'}
        strokeWidth={isPinned ? 1.5 : 0}
      />

      {/* Clipped animated bar body: resting solid navy OR expanded 4-band multi-color distribution */}
      <g clipPath={`url(#${clipId})`}>
        {/* Resting solid mean bar */}
        <motion.rect
          x={x}
          y={y}
          width={fullWidth}
          height={height}
          fill={
            payload.isMeasuredZero
              ? 'var(--status-danger-fg)'
              : 'var(--color-meanValue, var(--accent-primary))'
          }
          initial={false}
          animate={{ opacity: isExpanded ? 0 : 1 }}
          transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
        />

        {/* Expanded 4-band distribution segments (0–100% of bar width) */}
        <motion.g
          initial={false}
          animate={{ opacity: isExpanded ? 1 : 0 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        >
          {segments.map((seg, idx) => (
            <g key={seg.key}>
              <rect
                x={seg.segX}
                y={y}
                width={Math.max(seg.segWidth - (idx < segments.length - 1 ? 1.5 : 0), 1)}
                height={height}
                fill={seg.fill}
              />
              {seg.segWidth >= 56 && (
                <text
                  x={seg.segX + seg.segWidth / 2}
                  y={y + height / 2 + 4}
                  textAnchor="middle"
                  fill={seg.textFill}
                  fontSize={11}
                  fontWeight={600}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontVariantNumeric: 'tabular-nums',
                    pointerEvents: 'none',
                  }}
                >
                  {seg.count}
                </text>
              )}
            </g>
          ))}
        </motion.g>
      </g>

      {/* Resting PO Name Label inside the bar (or right beside if bar is narrow) */}
      <AnimatePresence initial={false}>
        {!isExpanded && (
          <motion.text
            key="resting-label"
            x={labelFitsInsideResting ? x + 10 : x + restingWidth + 10}
            y={y + height / 2 + 4}
            fill={
              labelFitsInsideResting
                ? 'var(--accent-contrast)'
                : 'var(--text-primary)'
            }
            fontSize={12}
            fontWeight={500}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.14 }}
            style={{ pointerEvents: 'none' }}
          >
            {labelFitsInsideResting
              ? truncateLabel(payload.displayLabel, maxInsideChars)
              : truncateLabel(
                  payload.displayLabel,
                  Math.max(12, Math.floor((fullWidth - restingWidth - 20) / 7)),
                )}
          </motion.text>
        )}
      </AnimatePresence>

      {/* Right-hand tabular-mono score (resting) or n/coverage readout (expanded) */}
      <text
        x={x + fullWidth + 10}
        y={y + height / 2 + 4}
        fill="var(--text-primary)"
        fontSize={12}
        fontWeight={600}
        style={{
          fontFamily: 'var(--font-mono)',
          fontVariantNumeric: 'tabular-nums slashed-zero',
          pointerEvents: 'none',
        }}
      >
        {isExpanded
          ? `n=${payload.n} · ${payload.coveragePct}`
          : payload.rawMean ?? '0.0'}
      </text>
    </g>
  );
}

function PoChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: ReadonlyArray<TooltipPayloadItem>;
}) {
  if (!active || !payload?.length) return null;
  const datum = payload[0]?.payload as PoChartDatum | undefined;
  if (!datum) return null;

  return (
    <div className="min-w-[230px] rounded-[var(--radius-card,10px)] border border-border bg-popover p-3 text-xs text-popover-foreground shadow-[var(--shadow-lg)]">
      <div className="flex items-baseline justify-between gap-3 border-b border-border/70 pb-2">
        <span className="tabular-mono font-semibold text-foreground">
          {datum.code}
        </span>
        <span className="tabular-mono text-muted-foreground">
          n = {datum.n} / {datum.populationSize} ({datum.coveragePct})
        </span>
      </div>
      <p className="mt-1.5 text-muted-foreground">{datum.label}</p>

      {datum.isUnassessed ? (
        <p className="mt-2 font-medium text-muted-foreground">
          — Not assessed (0 measured students)
        </p>
      ) : (
        <>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-muted-foreground">Cohort mean</span>
            <span className="tabular-mono font-semibold text-foreground">
              {datum.rawMean} / 100
            </span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-border/60 pt-2">
            {DISTRIBUTION_BANDS.map((band) => {
              const count = datum.distribution[band.key];
              const pct =
                datum.n > 0 ? Math.round((count / datum.n) * 100) : 0;
              return (
                <div
                  key={band.key}
                  className="flex items-center justify-between gap-2"
                >
                  <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                    <span
                      className={`size-2 rounded-[2px] ${band.swatchClass}`}
                      aria-hidden="true"
                    />
                    <span className="tabular-mono">{band.label}</span>
                  </span>
                  <span className="tabular-mono font-semibold text-foreground">
                    {count}{' '}
                    <span className="font-normal text-muted-foreground">
                      ({pct}%)
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

export interface PoAttainmentBarChartProps {
  outcomes: CohortOutcomeMetric[];
}

export function PoAttainmentBarChart({ outcomes }: PoAttainmentBarChartProps) {
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);
  const [pinnedCode, setPinnedCode] = useState<string | null>(null);

  const chartData = useMemo<PoChartDatum[]>(
    () =>
      outcomes.map((outcome) => {
        const isUnassessed = outcome.n === 0 || outcome.mean === null;
        const parsed = outcome.mean !== null ? Number(outcome.mean) : 0;
        const safeMean =
          !isUnassessed && Number.isFinite(parsed)
            ? Math.max(0, Math.min(100, parsed))
            : 0;
        const isMeasuredZero = !isUnassessed && safeMean === 0;
        return {
          code: outcome.code,
          label: outcome.label,
          displayLabel: `${outcome.code} · ${outcome.label}`,
          meanValue: safeMean,
          rawMean: outcome.mean,
          n: outcome.n,
          populationSize: outcome.population_size,
          coveragePct: formatCoveragePercent(outcome.coverage),
          isMeasuredZero,
          isUnassessed,
          distribution: outcome.distribution,
          outcome,
        };
      }),
    [outcomes],
  );

  const activeDatum = useMemo(() => {
    const code = hoveredCode ?? pinnedCode;
    if (!code) return null;
    return chartData.find((d) => d.code === code) ?? null;
  }, [chartData, hoveredCode, pinnedCode]);

  const rowHeight = 42;
  const chartHeight = Math.max(120, chartData.length * rowHeight + 24);
  const hasMeasuredOutcomes = chartData.some((d) => !d.isUnassessed);

  function handleTogglePin(code: string) {
    setPinnedCode((prev) => (prev === code ? null : code));
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="space-y-3 rounded-[var(--radius-card,10px)] border border-border/80 bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            Hover or click any measured PO bar to expand its full 100% 4-band
            student distribution. Dashed rule marks 70.0 target.
          </span>
          {pinnedCode && (
            <button
              type="button"
              onClick={() => setPinnedCode(null)}
              className="font-medium text-[var(--accent-primary)] underline-offset-4 hover:underline"
            >
              Collapse pinned ({pinnedCode})
            </button>
          )}
        </div>

        {/* Interactive shadcn / Recharts Horizontal Bar Chart */}
        <ChartContainer
          config={PO_CHART_CONFIG}
          className="w-full"
          style={{ height: `${chartHeight}px` }}
        >
          <BarChart
            accessibilityLayer
            data={chartData}
            layout="vertical"
            margin={{ left: 0, right: 92, top: 8, bottom: 8 }}
            barCategoryGap={8}
          >
            <CartesianGrid
              horizontal={false}
              stroke="var(--border-hairline)"
              strokeDasharray="3 3"
            />
            <YAxis
              dataKey="code"
              type="category"
              tickLine={false}
              axisLine={false}
              hide
            />
            <XAxis type="number" domain={[0, 100]} hide />
            <ReferenceLine
              x={70}
              stroke="var(--accent-primary)"
              strokeOpacity={0.4}
              strokeDasharray="4 4"
            />
            <ChartTooltip
              cursor={false}
              content={<PoChartTooltip />}
            />
            <Bar
              dataKey="meanValue"
              fill="var(--color-meanValue)"
              radius={6}
              barSize={30}
              isAnimationActive={false}
              background={{ fill: 'transparent' }}
              shape={(props: unknown) => {
                const barProps = props as Omit<
                  CustomBarShapeProps,
                  'activeCode' | 'pinnedCode' | 'onHover' | 'onTogglePin'
                >;
                return (
                  <InteractivePoBarShape
                    {...barProps}
                    activeCode={hoveredCode}
                    pinnedCode={pinnedCode}
                    onHover={setHoveredCode}
                    onTogglePin={handleTogglePin}
                  />
                );
              }}
            />
          </BarChart>
        </ChartContainer>

        {/* Live Inspector Strip (shows exact band counts for hovered/pinned PO) */}
        <AnimatePresence initial={false} mode="wait">
          {activeDatum && !activeDatum.isUnassessed && (
            <motion.div
              key={activeDatum.code}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 2 }}
              transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
              className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-input,6px)] border border-[var(--accent-border)] bg-[var(--accent-soft)]/50 px-3 py-2 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="tabular-mono font-semibold text-foreground">
                  {activeDatum.code}
                </span>
                <span className="text-muted-foreground">
                  {activeDatum.label}
                </span>
                {activeDatum.isMeasuredZero ? (
                  <MeasuredZeroTag value="0.0" />
                ) : (
                  <span className="tabular-mono font-semibold text-foreground">
                    Mean {activeDatum.rawMean}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {DISTRIBUTION_BANDS.map((band) => (
                  <span
                    key={band.key}
                    className="inline-flex items-center gap-1.5 text-muted-foreground"
                  >
                    <span
                      className={`size-2 rounded-[2px] ${band.swatchClass}`}
                      aria-hidden="true"
                    />
                    <span className="tabular-mono">
                      {band.label}:{' '}
                      <strong className="font-semibold text-foreground">
                        {activeDatum.distribution[band.key]}
                      </strong>
                    </span>
                  </span>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Accessible screen-reader & SSR summary mirror for every PO */}
        <div
          className="sr-only"
          {...(hasMeasuredOutcomes
            ? {
                role: 'img',
                'aria-label': `PO1–PO11 horizontal attainment chart for ${chartData.length} program outcomes`,
              }
            : {})}
        >
          {chartData.map((item) => (
            <div key={item.code}>
              <span>{item.code}</span>{' '}
              <span>{item.label}</span>{' '}
              {item.isUnassessed ? (
                <NotAssessedText />
              ) : (
                <>
                  <span>Mean: {item.rawMean}</span>{' '}
                  {item.isMeasuredZero && <MeasuredZeroTag value="0.0" />}{' '}
                  <span>
                    n = {item.n} ({item.n} / {item.populationSize})
                  </span>{' '}
                  <span>Coverage: {item.coveragePct}</span>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </MotionConfig>
  );
}
