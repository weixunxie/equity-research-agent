import { fmtPrice } from "@/lib/format";
import type { Analysis, ResearchData, SentimentLabel, Stance } from "@/lib/types";

const STANCE: Record<Stance, { label: string; glyph: string; cls: string }> = {
  bullish: { label: "Bullish lean", glyph: "▲", cls: "text-up" },
  neutral: { label: "Neutral lean", glyph: "●", cls: "text-ink2" },
  bearish: { label: "Bearish lean", glyph: "▼", cls: "text-down" },
};

const SENTIMENT: Record<SentimentLabel, { label: string; glyph: string; cls: string }> = {
  positive: { label: "Positive news flow", glyph: "▲", cls: "text-up" },
  neutral: { label: "Neutral news flow", glyph: "●", cls: "text-ink2" },
  mixed: { label: "Mixed news flow", glyph: "◆", cls: "text-warn" },
  negative: { label: "Negative news flow", glyph: "▼", cls: "text-down" },
};

function Badge({ glyph, label, cls }: { glyph: string; label: string; cls: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink">
      <span className={`text-[10px] ${cls}`} aria-hidden>
        {glyph}
      </span>
      {label}
    </span>
  );
}

/** Position of the current price inside the 52-week range. */
function YearRange({ low, high, current, currency }: { low: number; high: number; current: number; currency?: string | null }) {
  const pct = Math.max(0, Math.min(100, ((current - low) / (high - low)) * 100));
  return (
    <div className="mt-4 max-w-xs">
      <div className="flex justify-between text-xs text-muted">
        <span>52-week range</span>
        <span className="num">
          {fmtPrice(low, currency)} – {fmtPrice(high, currency)}
        </span>
      </div>
      <div className="relative mt-2 h-1.5 rounded-full bg-sunken">
        <span
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-ink"
          style={{ left: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function Hero({
  data,
  analysis,
  analysisPending,
  insufficient = false,
}: {
  data: ResearchData;
  analysis: Analysis | null;
  analysisPending: boolean;
  /** The run found no filings or fundamentals, so no view was formed. */
  insufficient?: boolean;
}) {
  const { financials } = data;
  const price = financials.price ?? {};
  const profile = financials.profile ?? {};
  const change = price.change_pct;
  const stance = analysis ? STANCE[analysis.stance] : null;
  const sentiment = analysis ? SENTIMENT[analysis.recent_sentiment.label] : null;

  return (
    <section className="card grid gap-8 p-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-ink px-2 py-0.5 text-xs font-semibold tracking-wide text-page">
            {data.ticker}
          </span>
          {profile.sector ? (
            <span className="text-xs text-muted">
              {profile.sector}
              {profile.industry ? ` · ${profile.industry}` : ""}
            </span>
          ) : null}
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink">{data.company}</h1>

        <div className="mt-5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-5xl font-semibold tracking-tight text-ink">
            {fmtPrice(price.current, financials.currency)}
          </span>
          {change != null ? (
            <span className={`num text-sm font-semibold ${change >= 0 ? "text-up" : "text-down"}`}>
              <span aria-hidden>{change >= 0 ? "▲" : "▼"}</span> {Math.abs(change).toFixed(2)}%
              <span className="font-normal text-muted"> vs. previous close</span>
            </span>
          ) : null}
        </div>

        {price.fifty_two_week_low != null &&
        price.fifty_two_week_high != null &&
        price.current != null &&
        price.fifty_two_week_high > price.fifty_two_week_low ? (
          <YearRange
            low={price.fifty_two_week_low}
            high={price.fifty_two_week_high}
            current={price.current}
            currency={financials.currency}
          />
        ) : null}
      </div>

      <div className="lg:border-l lg:border-grid lg:pl-8">
        <div className="eyebrow">Thesis</div>
        {analysis ? (
          <>
            <p className="mt-2 text-[15px] leading-relaxed text-ink">{analysis.thesis}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {stance ? <Badge {...stance} /> : null}
              {sentiment ? <Badge {...sentiment} /> : null}
            </div>
            <p className="mt-3 text-sm text-ink2">{analysis.stance_rationale}</p>
          </>
        ) : analysisPending ? (
          <div className="mt-3 space-y-2.5" aria-label="Analysis in progress">
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-11/12" />
            <div className="skeleton h-4 w-3/4" />
            <div className="skeleton mt-4 h-6 w-40 rounded-full" />
          </div>
        ) : insufficient ? (
          <>
            <p className="mt-2 text-[15px] font-medium text-ink">Not enough source data to form a view.</p>
            <p className="mt-2 text-sm text-ink2">
              No SEC filings or financial statements were found for {data.ticker}, so no thesis was
              written. See Sources &amp; run details for what was checked.
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">No analysis was produced for this run.</p>
        )}
      </div>
    </section>
  );
}
