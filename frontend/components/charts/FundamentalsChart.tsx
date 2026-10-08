"use client";

import { useMemo, useState } from "react";

import { fmtMoney, fmtMonthYear, fmtPct, niceTicks, yearOf } from "@/lib/format";
import type { StatementPeriod } from "@/lib/types";
import { useWidth } from "./useWidth";

const HEIGHT = 260;
const MARGIN = { top: 12, right: 8, bottom: 26, left: 52 };
const BAR_MAX = 24;
const BAR_GAP = 2; // surface gap between the two bars of a period
const RADIUS = 4;
const TOOLTIP_WIDTH = 176;

const SERIES = [
  { key: "revenue", label: "Revenue", color: "var(--series-1)" },
  { key: "net_income", label: "Net income", color: "var(--series-2)" },
] as const;

/** A column from the zero line to `y1`: rounded at the data end, square at the baseline. */
function columnPath(x: number, y0: number, y1: number, w: number): string {
  const h = Math.abs(y1 - y0);
  const r = Math.min(RADIUS, w / 2, h);
  const dir = y1 < y0 ? -1 : 1; // -1: grows upward
  return [
    `M${x},${y0}`,
    `L${x},${y1 - dir * r}`,
    `Q${x},${y1} ${x + r},${y1}`,
    `L${x + w - r},${y1}`,
    `Q${x + w},${y1} ${x + w},${y1 - dir * r}`,
    `L${x + w},${y0}Z`,
  ].join("");
}

export default function FundamentalsChart({
  periods,
  currency,
  mode,
}: {
  periods: StatementPeriod[];
  currency?: string | null;
  mode: "quarterly" | "annual";
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const label = (p: StatementPeriod) =>
    mode === "annual" ? `FY${yearOf(p.period)}` : fmtMonthYear(p.period);

  const layout = useMemo(() => {
    if (width === 0 || periods.length === 0) return null;
    const innerW = width - MARGIN.left - MARGIN.right;
    const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
    const values = periods.flatMap((p) => [p.revenue ?? 0, p.net_income ?? 0]);
    const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values), 4);
    const yMin = Math.min(0, ...values, ticks[0]);
    const yMax = Math.max(...values, ticks[ticks.length - 1]);

    const band = innerW / periods.length;
    const barW = Math.max(4, Math.min(BAR_MAX, (band * 0.6 - BAR_GAP) / 2));
    const y = (v: number) => MARGIN.top + (1 - (v - yMin) / (yMax - yMin || 1)) * innerH;
    const bandX = (i: number) => MARGIN.left + i * band;
    return { innerW, innerH, band, barW, y, bandX, ticks };
  }, [periods, width]);

  if (periods.length === 0) {
    return <p className="py-10 text-center text-sm text-muted">No income statement data available.</p>;
  }

  const active = hover === null ? null : periods[hover];

  return (
    <div>
      <div className="mb-2 flex items-center gap-4 text-xs text-ink2">
        {SERIES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>

      <div ref={ref} className="relative">
        {layout && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={`Revenue and net income by ${mode === "annual" ? "fiscal year" : "quarter"}: ${periods
              .map((p) => `${label(p)} revenue ${fmtMoney(p.revenue, currency)}, net income ${fmtMoney(p.net_income, currency)}`)
              .join("; ")}.`}
          >
            {layout.ticks.map((t) => (
              <g key={t}>
                <line
                  x1={MARGIN.left}
                  x2={MARGIN.left + layout.innerW}
                  y1={layout.y(t)}
                  y2={layout.y(t)}
                  stroke={t === 0 ? "var(--axis)" : "var(--grid)"}
                />
                <text
                  x={MARGIN.left - 8}
                  y={layout.y(t)}
                  dy="0.32em"
                  fontSize={11}
                  fill="var(--muted)"
                  textAnchor="end"
                  className="num"
                >
                  {fmtMoney(t, currency, 0)}
                </text>
              </g>
            ))}

            {periods.map((p, i) => {
              const cx = layout.bandX(i) + layout.band / 2;
              const x0 = cx - layout.barW - BAR_GAP / 2;
              return (
                <g key={p.period}>
                  {hover === i ? (
                    <rect
                      x={layout.bandX(i) + 4}
                      y={MARGIN.top}
                      width={layout.band - 8}
                      height={layout.innerH}
                      rx={6}
                      fill="var(--sunken)"
                    />
                  ) : null}
                  {SERIES.map((s, k) => {
                    const v = p[s.key];
                    if (v === undefined) return null;
                    return (
                      <path
                        key={s.key}
                        d={columnPath(
                          x0 + k * (layout.barW + BAR_GAP),
                          layout.y(0),
                          layout.y(v),
                          layout.barW,
                        )}
                        fill={s.color}
                      />
                    );
                  })}
                  <text
                    x={cx}
                    y={HEIGHT - 8}
                    fontSize={11}
                    fill={hover === i ? "var(--ink)" : "var(--muted)"}
                    textAnchor="middle"
                  >
                    {label(p)}
                  </text>
                  <rect
                    x={layout.bandX(i)}
                    y={0}
                    width={layout.band}
                    height={HEIGHT}
                    fill="transparent"
                    tabIndex={0}
                    aria-label={`${label(p)}: revenue ${fmtMoney(p.revenue, currency)}, net income ${fmtMoney(p.net_income, currency)}`}
                    className="outline-none"
                    onPointerEnter={() => setHover(i)}
                    onPointerLeave={() => setHover(null)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                  />
                </g>
              );
            })}
          </svg>
        )}

        {layout && active && hover !== null ? (
          <div
            className="pointer-events-none absolute top-1 rounded-lg bg-surface px-3 py-2 text-xs shadow-pop"
            style={{
              width: TOOLTIP_WIDTH,
              // Beside the hovered period, not over its bars; flips at the right edge.
              left:
                layout.bandX(hover) + layout.band + TOOLTIP_WIDTH > width
                  ? Math.max(0, layout.bandX(hover) - TOOLTIP_WIDTH)
                  : layout.bandX(hover) + layout.band,
            }}
          >
            <div className="mb-1 text-muted">{label(active)}</div>
            {SERIES.map((s) => (
              <div key={s.key} className="flex items-center justify-between gap-3 py-0.5">
                <span className="inline-flex items-center gap-1.5 text-ink2">
                  <span className="h-0.5 w-3 rounded" style={{ background: s.color }} />
                  {s.label}
                </span>
                <span className="num font-semibold text-ink">{fmtMoney(active[s.key], currency)}</span>
              </div>
            ))}
            <div className="mt-1 flex justify-between gap-3 border-t border-grid pt-1 text-ink2">
              <span>Net margin</span>
              <span className="num font-semibold text-ink">
                {active.revenue && active.net_income !== undefined
                  ? fmtPct(active.net_income / active.revenue)
                  : "—"}
              </span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
