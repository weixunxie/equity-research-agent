import { fmtPrice, fmtSignedPct } from "@/lib/format";
import type { Financials } from "@/lib/types";

/** Where the current price sits against the sell-side target range. */
export default function TargetRange({ financials }: { financials: Financials }) {
  const { target_low: low, target_mean: mean, target_high: high } = financials.analyst ?? {};
  const current = financials.price?.current;
  const currency = financials.currency;
  if (low == null || mean == null || high == null || current == null || high <= low) {
    return <p className="text-sm text-muted">No analyst price targets available.</p>;
  }

  // The scale spans the target range, widened to include the price if it sits outside.
  const min = Math.min(low, current);
  const max = Math.max(high, current);
  const pos = (v: number) => `${((v - min) / (max - min)) * 100}%`;
  const upside = financials.analyst?.upside_to_mean;
  const count = financials.analyst?.analyst_count;
  const rec = financials.analyst?.recommendation?.replace(/_/g, " ");

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="text-sm text-ink2">
          Mean target <span className="num font-semibold text-ink">{fmtPrice(mean, currency)}</span>
          {upside != null ? (
            <span className="num"> · {fmtSignedPct(upside)} vs. price</span>
          ) : null}
        </div>
        <div className="text-xs text-muted">
          {rec ? <span className="capitalize">{rec}</span> : null}
          {rec && count ? " · " : null}
          {count ? `${Math.round(count)} analysts` : null}
        </div>
      </div>

      <div
        className="relative mt-9 h-2"
        role="img"
        aria-label={`Analyst targets range from ${fmtPrice(low, currency)} to ${fmtPrice(high, currency)} with a mean of ${fmtPrice(mean, currency)}; the current price is ${fmtPrice(current, currency)}.`}
      >
        <div className="absolute inset-0 rounded-full bg-sunken" />
        <div
          className="absolute inset-y-0 rounded-full bg-series1 opacity-30"
          style={{ left: pos(low), right: `calc(100% - ${pos(high)})` }}
        />
        {/* Mean target: a tick on the track. */}
        <div
          className="absolute -top-1 h-4 w-0.5 -translate-x-1/2 rounded bg-series1"
          style={{ left: pos(mean) }}
        />
        {/* Current price: a ringed dot with its value above. */}
        <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: pos(current) }}>
          <div className="h-3.5 w-3.5 rounded-full border-2 border-surface bg-ink" />
          <div className="num absolute bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-ink">
            {fmtPrice(current, currency)}
          </div>
        </div>
      </div>

      <div className="num mt-2 flex justify-between text-xs text-muted">
        <span>Low {fmtPrice(low, currency)}</span>
        <span>High {fmtPrice(high, currency)}</span>
      </div>
      <div className="mt-2 flex items-center gap-4 text-xs text-ink2">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-ink" /> Current price
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-0.5 rounded bg-series1" /> Mean target
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-full bg-series1 opacity-30" /> Target range
        </span>
      </div>
    </div>
  );
}
