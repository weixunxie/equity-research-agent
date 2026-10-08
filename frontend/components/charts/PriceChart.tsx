"use client";

import { useMemo, useState } from "react";

import { fmtDate, fmtPrice, fmtSignedPct, monthOf, niceTicks } from "@/lib/format";
import type { PricePoint } from "@/lib/types";
import { useWidth } from "./useWidth";

const HEIGHT = 260;
const MARGIN = { top: 12, right: 52, bottom: 26, left: 4 };
const TOOLTIP_WIDTH = 150;

export default function PriceChart({
  points,
  currency,
}: {
  points: PricePoint[];
  currency?: string | null;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const layout = useMemo(() => {
    if (width === 0 || points.length < 2) return null;
    const innerW = width - MARGIN.left - MARGIN.right;
    const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
    const closes = points.map((p) => p.close);
    const lo = Math.min(...closes);
    const hi = Math.max(...closes);
    const pad = (hi - lo) * 0.08 || hi * 0.05;
    const ticks = niceTicks(lo - pad, hi + pad, 4);
    const yMin = Math.min(lo - pad, ticks[0]);
    const yMax = Math.max(hi + pad, ticks[ticks.length - 1]);

    const x = (i: number) => MARGIN.left + (i / (points.length - 1)) * innerW;
    const y = (v: number) => MARGIN.top + (1 - (v - yMin) / (yMax - yMin)) * innerH;

    const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.close).toFixed(1)}`).join("");
    const base = MARGIN.top + innerH;
    const area = `${line}L${x(points.length - 1).toFixed(1)},${base}L${x(0).toFixed(1)},${base}Z`;

    // One x tick at the first trading day of each month, thinned to fit.
    const monthStarts = points
      .map((p, i) => ({ i, month: p.date.slice(0, 7) }))
      .filter((m, k, all) => k > 0 && m.month !== all[k - 1].month);
    const every = Math.max(1, Math.ceil((monthStarts.length * 44) / innerW));
    const xTicks = monthStarts.filter((_, k) => k % every === 0);

    return { innerW, innerH, x, y, line, area, ticks, xTicks, base };
  }, [points, width]);

  if (points.length < 2) {
    return <p className="py-10 text-center text-sm text-muted">No price history available.</p>;
  }

  const first = points[0];
  const last = points[points.length - 1];
  const active = hover === null ? null : points[hover];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    if (!layout) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    setHover(Math.max(0, Math.min(points.length - 1, Math.round(ratio * (points.length - 1)))));
  }

  return (
    <div ref={ref} className="relative">
      {layout && (
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`Daily closing price over the past year, from ${fmtPrice(first.close, currency)} on ${fmtDate(first.date)} to ${fmtPrice(last.close, currency)} on ${fmtDate(last.date)}.`}
        >
          {layout.ticks.map((t) => (
            <g key={t}>
              <line
                x1={MARGIN.left}
                x2={MARGIN.left + layout.innerW}
                y1={layout.y(t)}
                y2={layout.y(t)}
                stroke="var(--grid)"
              />
              <text
                x={MARGIN.left + layout.innerW + 8}
                y={layout.y(t)}
                dy="0.32em"
                fontSize={11}
                fill="var(--muted)"
                className="num"
              >
                {t.toLocaleString("en-US")}
              </text>
            </g>
          ))}
          {layout.xTicks.map(({ i }) => (
            <text
              key={i}
              x={layout.x(i)}
              y={HEIGHT - 8}
              fontSize={11}
              fill="var(--muted)"
              textAnchor="middle"
            >
              {monthOf(points[i].date)}
            </text>
          ))}

          <path d={layout.area} fill="var(--series-1)" opacity={0.1} />
          <path
            d={layout.line}
            fill="none"
            stroke="var(--series-1)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {active && hover !== null ? (
            <line
              x1={layout.x(hover)}
              x2={layout.x(hover)}
              y1={MARGIN.top}
              y2={layout.base}
              stroke="var(--axis)"
            />
          ) : null}
          <circle
            cx={layout.x(hover ?? points.length - 1)}
            cy={layout.y((active ?? last).close)}
            r={4.5}
            fill="var(--series-1)"
            stroke="var(--surface)"
            strokeWidth={2}
          />

          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={layout.innerW}
            height={layout.innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
      )}

      {layout && active && hover !== null ? (
        <div
          className="pointer-events-none absolute top-1 rounded-lg bg-surface px-3 py-2 text-xs shadow-pop"
          style={{
            width: TOOLTIP_WIDTH,
            left: Math.max(
              0,
              layout.x(hover) + 12 + TOOLTIP_WIDTH > width
                ? layout.x(hover) - 12 - TOOLTIP_WIDTH
                : layout.x(hover) + 12,
            ),
          }}
        >
          <div className="num text-sm font-semibold text-ink">
            {fmtPrice(active.close, currency)}
          </div>
          <div className="text-muted">{fmtDate(active.date)}</div>
          <div className="num mt-1 text-ink2">
            {fmtSignedPct(active.close / first.close - 1)} since {monthOf(first.date)} {first.date.slice(8, 10)}
          </div>
        </div>
      ) : null}
    </div>
  );
}
