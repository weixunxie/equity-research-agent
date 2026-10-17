"use client";

import { useState } from "react";

import type { Analysis, ResearchData } from "@/lib/types";
import FundamentalsChart from "./charts/FundamentalsChart";
import PriceChart from "./charts/PriceChart";
import TargetRange from "./charts/TargetRange";
import Hero from "./Hero";
import KpiGrid from "./KpiGrid";
import NewsList from "./NewsList";
import PeersTable from "./PeersTable";
import Thesis, { ThesisSkeleton } from "./Thesis";
import { fmtSignedPct } from "@/lib/format";

function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg bg-sunken p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 font-medium transition ${
            value === o.value ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function Dashboard({
  data,
  analysis,
  analysisPending,
}: {
  data: ResearchData;
  analysis: Analysis | null;
  /** True while the Analyst is still working (shows placeholders). */
  analysisPending: boolean;
}) {
  const { financials } = data;
  // With no filings and no fundamentals the Analyst writes nothing, so there
  // is no analysis to wait for.
  const insufficient = data.insufficient_data === true;
  const pending = analysisPending && !insufficient;
  const hasQuarterly = (financials.quarterly?.length ?? 0) > 0;
  const [mode, setMode] = useState<"quarterly" | "annual">(hasQuarterly ? "quarterly" : "annual");
  const history = financials.price_history ?? [];
  const yearChange =
    history.length > 1 ? history[history.length - 1].close / history[0].close - 1 : null;

  return (
    <div className="space-y-4">
      <Hero data={data} analysis={analysis} analysisPending={pending} insufficient={insufficient} />
      <KpiGrid financials={financials} />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-6">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="eyebrow">Share price · 1 year</h2>
            {yearChange !== null ? (
              <span className={`num text-sm font-semibold ${yearChange >= 0 ? "text-up" : "text-down"}`}>
                <span aria-hidden>{yearChange >= 0 ? "▲" : "▼"}</span>{" "}
                {fmtSignedPct(yearChange).replace(/^[+-]/, "")}
              </span>
            ) : null}
          </div>
          <PriceChart points={history} currency={financials.currency} />
        </section>

        <section className="card p-6">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="eyebrow">Revenue &amp; net income</h2>
            <Segmented
              label="Reporting period"
              value={mode}
              onChange={setMode}
              options={[
                { value: "quarterly", label: "Quarterly" },
                { value: "annual", label: "Annual" },
              ]}
            />
          </div>
          <FundamentalsChart
            periods={(mode === "quarterly" ? financials.quarterly : financials.annual) ?? []}
            currency={financials.currency}
            mode={mode}
          />
        </section>
      </div>

      {analysis ? <Thesis analysis={analysis} /> : pending ? <ThesisSkeleton /> : null}

      <section className="card p-6">
        <h2 className="eyebrow">Valuation vs. peers</h2>
        {analysis ? (
          <p className="mt-3 max-w-4xl text-sm leading-relaxed text-ink2">{analysis.valuation_view}</p>
        ) : null}
        <div className="mt-4">
          <PeersTable
            company={data.company}
            financials={financials}
            peers={data.peers}
            basis={data.metadata.peer_basis}
          />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section className="card self-start p-6">
          <h2 className="eyebrow mb-4">Analyst price targets</h2>
          <TargetRange financials={financials} />
        </section>
        <section className="card p-6">
          <h2 className="eyebrow mb-3">Recent news</h2>
          <NewsList news={data.news} sentiment={analysis?.recent_sentiment ?? null} />
        </section>
      </div>
    </div>
  );
}
