import type { Analysis, Severity } from "@/lib/types";

const SEVERITY: Record<Severity, { label: string; dots: number }> = {
  high: { label: "High", dots: 3 },
  medium: { label: "Medium", dots: 2 },
  low: { label: "Low", dots: 1 },
};

function PointList({ items, tone }: { items: string[]; tone: "up" | "down" | "neutral" }) {
  const marker = tone === "up" ? "bg-up" : tone === "down" ? "bg-down" : "bg-axis";
  if (items.length === 0) return <p className="mt-3 text-sm text-muted">None identified.</p>;
  return (
    <ul className="mt-3 space-y-2.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 text-sm leading-relaxed text-ink2">
          <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${marker}`} aria-hidden />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function SeverityMeter({ severity }: { severity: Severity }) {
  const { label, dots } = SEVERITY[severity];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-ink2">
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((n) => (
          <span key={n} className={`h-1.5 w-1.5 rounded-full ${n <= dots ? "bg-ink" : "bg-grid"}`} />
        ))}
      </span>
      {label}
    </span>
  );
}

export function ThesisSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2" aria-label="Analysis in progress">
      {[0, 1].map((k) => (
        <div key={k} className="card space-y-3 p-6">
          <div className="skeleton h-3 w-24" />
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-4" style={{ width: `${95 - i * 9}%` }} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Bull vs. bear, catalysts, risks and the narrative reads from the Analyst. */
export default function Thesis({ analysis }: { analysis: Analysis }) {
  const order: Severity[] = ["high", "medium", "low"];
  const risks = [...analysis.key_risks].sort(
    (a, b) => order.indexOf(a.severity) - order.indexOf(b.severity),
  );
  const summary = analysis.financial_summary;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-6">
          <h2 className="eyebrow flex items-center gap-2">
            <span className="text-up" aria-hidden>▲</span> Bull case
          </h2>
          <PointList items={analysis.bull_case} tone="up" />
        </section>
        <section className="card p-6">
          <h2 className="eyebrow flex items-center gap-2">
            <span className="text-down" aria-hidden>▼</span> Bear case
          </h2>
          <PointList items={analysis.bear_case} tone="down" />
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <section className="card p-6">
          <h2 className="eyebrow">Key risks</h2>
          {risks.length === 0 ? (
            <p className="mt-3 text-sm text-muted">None identified.</p>
          ) : (
            <ul className="mt-1 divide-y divide-grid">
              {risks.map((risk, i) => (
                <li key={i} className="py-3 last:pb-0">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm font-semibold text-ink">{risk.title}</span>
                    <SeverityMeter severity={risk.severity} />
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-ink2">{risk.detail}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-4">
          <section className="card p-6">
            <h2 className="eyebrow">Catalysts</h2>
            <PointList items={analysis.catalysts} tone="neutral" />
          </section>
          <section className="card p-6">
            <h2 className="eyebrow">Business</h2>
            <p className="mt-3 text-sm leading-relaxed text-ink2">{analysis.business_overview}</p>
          </section>
        </div>
      </div>

      <section className="card grid gap-6 p-6 md:grid-cols-3">
        {[
          ["Revenue", summary.revenue_trend],
          ["Profitability", summary.profitability_trend],
          ["Balance sheet", summary.balance_sheet],
        ].map(([title, text]) => (
          <div key={title}>
            <h2 className="eyebrow">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink2">{text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
