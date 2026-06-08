import type { Phase, ResearchResponse, StepKey, StepStatus } from "@/lib/types";
import ProgressTracker from "./ProgressTracker";

interface SidebarProps {
  ticker: string;
  onTickerChange: (value: string) => void;
  onRun: () => void;
  phase: Phase;
  steps: Record<StepKey, StepStatus>;
  report: ResearchResponse | null;
}

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1">
      <span className="text-zinc-500">{label}</span>
      <span className="truncate text-right text-zinc-300">{value}</span>
    </div>
  );
}

export default function Sidebar({
  ticker,
  onTickerChange,
  onRun,
  phase,
  steps,
  report,
}: SidebarProps) {
  const isRunning = phase === "running";
  const meta = report?.metadata;

  return (
    <aside className="flex h-screen w-80 shrink-0 flex-col border-r border-zinc-800 bg-zinc-900/40">
      {/* Brand */}
      <div className="flex items-start justify-between border-b border-zinc-800 px-5 py-5">
        <div>
          <h1 className="text-sm font-semibold tracking-tight text-white">
            Equity Research Agent
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Researcher → Analyst → Writer
          </p>
          <p className="mt-2 text-[11px] text-zinc-600">
            by <span className="text-zinc-400">Stephanie Xie</span>
          </p>
        </div>
        <a
          href="https://github.com/weixunxie/equity-research-agent"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View source on GitHub"
          title="View on GitHub"
          className="shrink-0 text-zinc-500 transition hover:text-white"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-5 w-5" aria-hidden>
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
          </svg>
        </a>
      </div>

      {/* Input */}
      <form
        className="px-5 py-5"
        onSubmit={(e) => {
          e.preventDefault();
          onRun();
        }}
      >
        <label
          htmlFor="ticker"
          className="mb-1.5 block text-xs font-medium text-zinc-400"
        >
          Ticker symbol
        </label>
        <input
          id="ticker"
          value={ticker}
          onChange={(e) => onTickerChange(e.target.value.toUpperCase())}
          placeholder="AAPL"
          maxLength={10}
          autoComplete="off"
          spellCheck={false}
          className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm font-medium tracking-wide text-white placeholder-zinc-600 outline-none transition focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/40"
        />
        <button
          type="submit"
          disabled={isRunning || ticker.trim().length === 0}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-md bg-emerald-500 px-3 py-2 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
        >
          {isRunning ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-900/40 border-t-zinc-900" />
              Running…
            </>
          ) : (
            "Run Research"
          )}
        </button>
      </form>

      {/* Progress tracker */}
      {phase !== "idle" && (
        <div className="border-t border-zinc-800 px-5 py-5">
          <h2 className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
            Pipeline
          </h2>
          <ProgressTracker steps={steps} />
        </div>
      )}

      {/* Run metadata */}
      {meta && (
        <div className="mt-auto border-t border-zinc-800 px-5 py-4 text-xs">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            Run details
          </h2>
          <MetaRow label="Company" value={report?.company ?? "—"} />
          <MetaRow
            label="Filing"
            value={
              meta.sec_form
                ? `${meta.sec_form} · ${meta.filing_date ?? "n/a"}`
                : "n/a"
            }
          />
          <MetaRow label="MD&A chunks" value={meta.chunks_indexed ?? 0} />
          <MetaRow label="News items" value={meta.news_count ?? 0} />
          <MetaRow label="Model" value={meta.chat_model ?? "—"} />
          {report && report.errors.length > 0 && (
            <p className="mt-2 rounded bg-amber-500/10 px-2 py-1 text-[11px] text-amber-400">
              {report.errors.length} warning(s) — partial data
            </p>
          )}
        </div>
      )}
    </aside>
  );
}
