import { fmtDate } from "@/lib/format";
import type { ResearchData } from "@/lib/types";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-grid py-2 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="num text-right text-ink">{value}</dd>
    </div>
  );
}

/** What the run was built from: filings, news and pipeline diagnostics. */
export default function RunDetails({ data, errors }: { data: ResearchData; errors: string[] }) {
  const meta = data.metadata;
  const sections = meta.sections;
  const filings = data.sources.filter((s) => s.kind === "filing");
  const articles = data.sources.filter((s) => s.kind === "news");
  const chars = (n?: number) => (n ? `${Math.round(n / 1000)}k chars` : "not found");

  return (
    <div className="space-y-4">
      {errors.length > 0 ? (
        <section className="card p-6" role="status">
          <h2 className="eyebrow flex items-center gap-2">
            <span className="text-warn" aria-hidden>▲</span>
            {errors.length} {errors.length === 1 ? "warning" : "warnings"} — some data is partial
          </h2>
          <ul className="mt-3 space-y-1.5 text-sm text-ink2">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-6">
          <h2 className="eyebrow">Sources</h2>
          <h3 className="mt-4 text-xs font-medium text-muted">SEC filings</h3>
          {filings.length === 0 ? (
            <p className="mt-1 text-sm text-muted">No filing was retrieved.</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {filings.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-accent hover:underline">
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          )}
          <h3 className="mt-5 text-xs font-medium text-muted">News</h3>
          {articles.length === 0 ? (
            <p className="mt-1 text-sm text-muted">No articles were retrieved.</p>
          ) : (
            <ul className="mt-1 space-y-1.5">
              {articles.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-accent hover:underline">
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-6">
          <h2 className="eyebrow">Run details</h2>
          <dl className="mt-2">
            <Row
              label="Latest periodic filing"
              value={meta.sec_form ? `${meta.sec_form} · ${fmtDate(meta.filing_date)}` : "—"}
            />
            <Row
              label="Latest annual filing"
              value={meta.annual_form ? `${meta.annual_form} · ${fmtDate(meta.annual_filing_date)}` : "—"}
            />
            <Row label="MD&A" value={chars(sections?.mda)} />
            <Row label="Risk Factors" value={chars(sections?.risk_factors)} />
            <Row label="Business" value={chars(sections?.business)} />
            <Row
              label="Filing chunks indexed"
              value={`${meta.chunks_indexed ?? 0}${meta.rag_backend ? ` · ${meta.rag_backend} store` : ""}`}
            />
            <Row label="News articles" value={meta.news_count ?? 0} />
            <Row label="Peers compared" value={data.peers.length} />
            <Row label="Model" value={meta.chat_model ?? "—"} />
          </dl>
        </section>
      </div>
    </div>
  );
}
