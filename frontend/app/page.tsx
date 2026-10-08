"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import Dashboard from "@/components/Dashboard";
import Pipeline from "@/components/Pipeline";
import ReportView from "@/components/ReportView";
import RunDetails from "@/components/RunDetails";
import TopBar from "@/components/TopBar";
import { runResearchStream } from "@/lib/api";
import { fmtAgo } from "@/lib/format";
import { clearHistory, loadHistory, saveToHistory, type HistoryEntry } from "@/lib/history";
import type {
  Analysis,
  Phase,
  ResearchData,
  StepKey,
  StepStatus,
} from "@/lib/types";

const INITIAL_STEPS: Record<StepKey, StepStatus> = {
  researcher: "pending",
  analyst: "pending",
  writer: "pending",
};
const ALL_DONE: Record<StepKey, StepStatus> = {
  researcher: "done",
  analyst: "done",
  writer: "done",
};
const EXAMPLES = ["AAPL", "NVDA", "MSFT", "JPM", "TSLA"];

type Tab = "overview" | "report" | "sources";
const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "report", label: "Full report" },
  { key: "sources", label: "Sources & run details" },
];

function EmptyState({ onPick }: { onPick: (ticker: string) => void }) {
  return (
    <div className="mx-auto max-w-2xl py-16 text-center sm:py-24">
      <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
        A research note on any US-listed stock, in about a minute
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-ink2">
        Three agents read the latest SEC filings, pull market data and peers, scan recent news,
        then write up the thesis, the risks and the valuation — with every number sourced.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
        <span className="text-sm text-muted">Try</span>
        {EXAMPLES.map((t) => (
          <button key={t} type="button" className="btn font-semibold tracking-wide" onClick={() => onPick(t)}>
            {t}
          </button>
        ))}
      </div>
      <dl className="mt-14 grid gap-6 text-left sm:grid-cols-3">
        {[
          ["Researcher", "10-K / 10-Q sections from EDGAR, a year of prices, fundamentals, a peer set and the month’s news."],
          ["Analyst", "A thesis with bull and bear cases, ranked risks, catalysts and a peer-relative valuation view."],
          ["Writer", "A full note with financial tables and sources, ready to copy, download or print."],
        ].map(([title, text]) => (
          <div key={title} className="border-t border-axis pt-3">
            <dt className="text-sm font-semibold text-ink">{title}</dt>
            <dd className="mt-1 text-sm leading-relaxed text-ink2">{text}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function LoadingOverview() {
  return (
    <div className="space-y-4" aria-label="Gathering data">
      <div className="card grid gap-8 p-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="space-y-3">
          <div className="skeleton h-4 w-32" />
          <div className="skeleton h-7 w-56" />
          <div className="skeleton h-12 w-44" />
        </div>
        <div className="space-y-2.5">
          <div className="skeleton h-3 w-16" />
          <div className="skeleton h-4 w-full" />
          <div className="skeleton h-4 w-5/6" />
        </div>
      </div>
      <div className="card grid grid-cols-2 gap-px overflow-hidden bg-grid lg:grid-cols-4">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="space-y-2 bg-surface px-5 py-4">
            <div className="skeleton h-3 w-20" />
            <div className="skeleton h-7 w-24" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card h-80 p-6"><div className="skeleton h-full" /></div>
        <div className="card h-80 p-6"><div className="skeleton h-full" /></div>
      </div>
    </div>
  );
}

export default function Page() {
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [steps, setSteps] = useState<Record<StepKey, StepStatus>>(INITIAL_STEPS);
  const [data, setData] = useState<ResearchData | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [failure, setFailure] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  const abortRef = useRef<AbortController | null>(null);
  // Report tokens arrive far faster than React should re-render markdown, so
  // they accumulate here and flush to state once per animation frame.
  const pendingText = useRef("");
  const frame = useRef<number | null>(null);

  useEffect(() => {
    setHistory(loadHistory());
    return () => abortRef.current?.abort();
  }, []);

  const run = useCallback(async (symbol: string, refresh = false) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setTicker(symbol);
    setPhase("running");
    setSteps(INITIAL_STEPS);
    setData(null);
    setAnalysis(null);
    setMarkdown("");
    setErrors([]);
    setFailure(null);
    setTab("overview");
    pendingText.current = "";
    window.scrollTo({ top: 0 });

    await runResearchStream(
      symbol,
      {
        onStep: (step, status) => setSteps((prev) => ({ ...prev, [step]: status })),
        onData: (payload, errs) => {
          setData(payload);
          setErrors(errs);
        },
        onAnalysis: setAnalysis,
        onToken: (text) => {
          pendingText.current += text;
          if (frame.current === null) {
            frame.current = requestAnimationFrame(() => {
              frame.current = null;
              setMarkdown(pendingText.current);
            });
          }
        },
        onResult: (result) => {
          if (frame.current !== null) cancelAnimationFrame(frame.current);
          frame.current = null;
          setData(result);
          setAnalysis(result.analysis);
          setMarkdown(result.report_markdown);
          setErrors(result.errors);
          setSteps(ALL_DONE);
          setPhase("done");
          setHistory(saveToHistory(result));
        },
        onError: (message) => {
          setFailure(message);
          setPhase("error");
        },
      },
      { signal: controller.signal, refresh },
    );
  }, []);

  function stop() {
    abortRef.current?.abort();
    // Keep whatever already arrived; a run stopped before any data is a reset.
    setPhase(data ? "done" : "idle");
    setSteps((prev) =>
      Object.fromEntries(
        Object.entries(prev).map(([k, v]) => [k, v === "running" ? "pending" : v]),
      ) as Record<StepKey, StepStatus>,
    );
  }

  function openHistory(entry: HistoryEntry) {
    abortRef.current?.abort();
    const { report } = entry;
    setTicker(report.ticker);
    setData(report);
    setAnalysis(report.analysis);
    setMarkdown(report.report_markdown);
    setErrors(report.errors);
    setFailure(null);
    setSteps(ALL_DONE);
    setPhase("done");
    setTab("overview");
  }

  const running = phase === "running";
  const showWorkspace = running || data !== null;

  return (
    <div className="min-h-screen">
      <TopBar
        ticker={ticker}
        onTickerChange={setTicker}
        onRun={() => {
          const symbol = ticker.trim().toUpperCase();
          if (symbol) run(symbol);
        }}
        onStop={stop}
        running={running}
        history={history}
        onOpenHistory={openHistory}
        onClearHistory={() => {
          clearHistory();
          setHistory([]);
        }}
      />

      <main className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6">
        {failure ? (
          <div className="card mb-4 p-5" role="alert">
            <h2 className="text-sm font-semibold text-down">Research failed</h2>
            <p className="mt-1 text-sm text-ink2">{failure}</p>
          </div>
        ) : null}

        {!showWorkspace ? (
          failure ? null : <EmptyState onPick={run} />
        ) : (
          <div className="space-y-4">
            {running ? <Pipeline steps={steps} /> : null}

            <div className="no-print flex items-center justify-between gap-3 border-b border-line">
              <div role="tablist" aria-label="Report views" className="scroll-none -mb-px flex gap-1 overflow-x-auto">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    role="tab"
                    type="button"
                    aria-selected={tab === t.key}
                    onClick={() => setTab(t.key)}
                    className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition ${
                      tab === t.key
                        ? "border-ink text-ink"
                        : "border-transparent text-muted hover:text-ink"
                    }`}
                  >
                    {t.label}
                    {t.key === "sources" && errors.length > 0 ? (
                      <span className="num ml-1.5 rounded-full bg-sunken px-1.5 py-0.5 text-[11px] text-warn">
                        {errors.length}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
              {data?.metadata.generated_at && !running ? (
                <div className="flex shrink-0 items-center gap-2 pb-1.5 text-xs text-muted">
                  <span className="hidden sm:inline">
                    {data.metadata.cached ? "Cached report · " : "Generated "}
                    {fmtAgo(data.metadata.generated_at)}
                  </span>
                  <button type="button" className="btn px-2 py-1 text-xs" onClick={() => run(data.ticker, true)}>
                    Refresh
                  </button>
                </div>
              ) : null}
            </div>

            {tab === "overview" ? (
              data ? (
                <Dashboard
                  data={data}
                  analysis={analysis}
                  analysisPending={running && analysis === null}
                />
              ) : (
                <LoadingOverview />
              )
            ) : tab === "report" ? (
              <ReportView ticker={data?.ticker ?? ticker} markdown={markdown} streaming={running} />
            ) : data ? (
              <RunDetails data={data} errors={errors} />
            ) : (
              <p className="py-10 text-center text-sm text-muted">
                Sources appear once the Researcher finishes.
              </p>
            )}
          </div>
        )}

        <footer className="no-print mt-12 border-t border-line pt-4 text-xs text-muted">
          Built by Stephanie Xie. Reports are AI-generated from SEC filings, Yahoo Finance data and
          news search, for information only — not investment advice.
        </footer>
      </main>
    </div>
  );
}
