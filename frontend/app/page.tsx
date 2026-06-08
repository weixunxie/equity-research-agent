"use client";

import { useState } from "react";

import ReportView from "@/components/ReportView";
import Sidebar from "@/components/Sidebar";
import SkeletonLoader from "@/components/SkeletonLoader";
import { runResearchStream } from "@/lib/api";
import type { Phase, ResearchResponse, StepKey, StepStatus } from "@/lib/types";

const INITIAL_STEPS: Record<StepKey, StepStatus> = {
  researcher: "pending",
  analyst: "pending",
  writer: "pending",
};

function EmptyState() {
  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-emerald-400">
        <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 17l6-6 4 4 7-7" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M14 7h6v6" />
        </svg>
      </div>
      <h2 className="text-lg font-medium text-zinc-200">Generate a research report</h2>
      <p className="mt-1 max-w-sm text-sm text-zinc-500">
        Enter a ticker symbol in the sidebar and run the agent pipeline. The
        report renders here as each step completes.
      </p>
    </div>
  );
}

function ErrorState({ message }: { message: string | null }) {
  return (
    <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-5">
      <h2 className="text-sm font-semibold text-red-300">Research failed</h2>
      <p className="mt-1 text-sm text-red-200/80">{message ?? "Unknown error."}</p>
    </div>
  );
}

export default function Page() {
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [steps, setSteps] = useState<Record<StepKey, StepStatus>>(INITIAL_STEPS);
  const [report, setReport] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol || phase === "running") return;

    setPhase("running");
    setSteps(INITIAL_STEPS);
    setReport(null);
    setError(null);

    await runResearchStream(symbol, {
      onStep: (step, status) =>
        setSteps((prev) => ({ ...prev, [step]: status })),
      onResult: (data) => {
        setReport(data);
        setSteps({ researcher: "done", analyst: "done", writer: "done" });
        setPhase("done");
      },
      onError: (message) => {
        setError(message);
        setPhase("error");
      },
    });
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        ticker={ticker}
        onTickerChange={setTicker}
        onRun={handleRun}
        phase={phase}
        steps={steps}
        report={report}
      />

      <main className="scroll-thin flex-1 overflow-y-auto bg-zinc-950">
        <div className="mx-auto max-w-3xl px-8 py-10">
          {report ? (
            <ReportView report={report} />
          ) : phase === "running" ? (
            <SkeletonLoader />
          ) : phase === "error" ? (
            <ErrorState message={error} />
          ) : (
            <EmptyState />
          )}
        </div>
      </main>
    </div>
  );
}
