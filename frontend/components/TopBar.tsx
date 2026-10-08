"use client";

import { useEffect, useRef, useState } from "react";

import { fmtDate } from "@/lib/format";
import type { HistoryEntry } from "@/lib/history";

interface TopBarProps {
  ticker: string;
  onTickerChange: (value: string) => void;
  onRun: () => void;
  onStop: () => void;
  running: boolean;
  history: HistoryEntry[];
  onOpenHistory: (entry: HistoryEntry) => void;
  onClearHistory: () => void;
}

function HistoryMenu({
  history,
  onOpen,
  onClear,
}: {
  history: HistoryEntry[];
  onOpen: (entry: HistoryEntry) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        className="btn"
        aria-expanded={open}
        aria-haspopup="menu"
        disabled={history.length === 0}
        onClick={() => setOpen((v) => !v)}
      >
        <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
          <circle cx="10" cy="10" r="7" />
          <path d="M10 6v4l2.5 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="hidden sm:inline">History</span>
        {history.length > 0 ? <span className="num text-muted">{history.length}</span> : null}
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 z-30 mt-2 w-72 rounded-xl bg-surface p-1.5 shadow-pop">
          {history.map((entry) => (
            <button
              key={entry.report.ticker}
              role="menuitem"
              type="button"
              className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left hover:bg-sunken"
              onClick={() => {
                onOpen(entry);
                setOpen(false);
              }}
            >
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink">{entry.report.ticker}</span>
                <span className="block truncate text-xs text-muted">{entry.report.company}</span>
              </span>
              <span className="shrink-0 text-xs text-muted">{fmtDate(entry.savedAt.slice(0, 10))}</span>
            </button>
          ))}
          <button
            type="button"
            className="mt-1 w-full rounded-lg border-t border-grid px-3 py-2 text-left text-xs text-muted hover:text-ink"
            onClick={() => {
              onClear();
              setOpen(false);
            }}
          >
            Clear saved reports
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function TopBar({
  ticker,
  onTickerChange,
  onRun,
  onStop,
  running,
  history,
  onOpenHistory,
  onClearHistory,
}: TopBarProps) {
  return (
    <header className="no-print sticky top-0 z-20 border-b border-line bg-page">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
        <a href="/" className="flex shrink-0 items-center gap-2" aria-label="Equity Research Agent — home">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-page">
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth={2.2} aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l5-5 4 4 7-8" />
            </svg>
          </span>
          <span className="hidden text-sm font-semibold tracking-tight text-ink md:inline">
            Equity Research Agent
          </span>
        </a>

        <form
          className="flex min-w-0 flex-1 items-center gap-2 md:ml-4 md:max-w-sm"
          onSubmit={(e) => {
            e.preventDefault();
            onRun();
          }}
        >
          <label htmlFor="ticker" className="sr-only">
            Ticker symbol
          </label>
          <input
            id="ticker"
            value={ticker}
            onChange={(e) => onTickerChange(e.target.value.toUpperCase())}
            placeholder="Ticker, e.g. AAPL"
            maxLength={10}
            autoComplete="off"
            spellCheck={false}
            className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-medium tracking-wide text-ink placeholder:font-normal placeholder:tracking-normal placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent-wash"
          />
          {running ? (
            <button type="button" className="btn shrink-0" onClick={onStop}>
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={ticker.trim().length === 0}
              className="shrink-0 rounded-lg bg-accent px-3.5 py-1.5 text-sm font-semibold text-accent-ink transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              Run research
            </button>
          )}
        </form>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <HistoryMenu history={history} onOpen={onOpenHistory} onClear={onClearHistory} />
          <a
            href="https://github.com/weixunxie/equity-research-agent"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View source on GitHub"
            title="View on GitHub"
            className="hidden rounded-lg p-1.5 text-muted transition hover:text-ink sm:block"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" className="h-5 w-5" aria-hidden>
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}
