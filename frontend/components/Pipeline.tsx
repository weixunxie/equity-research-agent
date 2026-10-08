import type { StepKey, StepStatus } from "@/lib/types";

const STEP_META: { key: StepKey; label: string; desc: string }[] = [
  { key: "researcher", label: "Researcher", desc: "SEC filings, market data, peers, news" },
  { key: "analyst", label: "Analyst", desc: "Thesis, bull/bear, risks, valuation" },
  { key: "writer", label: "Writer", desc: "Full research note" },
];

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done") {
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3" aria-hidden>
          <path
            fillRule="evenodd"
            d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0l-3.5-3.5a1 1 0 1 1 1.4-1.4l2.8 2.8 6.8-6.8a1 1 0 0 1 1.4 0Z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-grid border-t-accent" />
    );
  }
  return <span className="h-5 w-5 shrink-0 rounded-full border-2 border-axis" />;
}

/** Live status of the three agents, driven by the API's step events. */
export default function Pipeline({ steps }: { steps: Record<StepKey, StepStatus> }) {
  return (
    <ol className="no-print card grid gap-px overflow-hidden bg-grid sm:grid-cols-3" aria-label="Pipeline progress">
      {STEP_META.map((meta) => {
        const status = steps[meta.key];
        return (
          <li
            key={meta.key}
            className="flex items-center gap-3 bg-surface px-4 py-3"
            aria-current={status === "running" ? "step" : undefined}
          >
            <StepIcon status={status} />
            <div className="min-w-0">
              <div className={`text-sm font-medium ${status === "pending" ? "text-muted" : "text-ink"}`}>
                {meta.label}
                <span className="sr-only"> — {status}</span>
              </div>
              <div className="truncate text-xs text-muted">{meta.desc}</div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
