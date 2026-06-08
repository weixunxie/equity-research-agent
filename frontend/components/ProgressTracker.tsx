import type { StepKey, StepStatus } from "@/lib/types";

const STEP_META: { key: StepKey; label: string; desc: string }[] = [
  { key: "researcher", label: "Researcher", desc: "SEC filings · financials · news" },
  { key: "analyst", label: "Analyst", desc: "Bull/bear · risks · RAG" },
  { key: "writer", label: "Writer", desc: "Markdown report" },
];

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "Pending",
  running: "Running…",
  done: "Done",
};

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done") {
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-zinc-950">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
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
      <span className="h-6 w-6 shrink-0 animate-spin rounded-full border-2 border-emerald-500/25 border-t-emerald-400" />
    );
  }
  return <span className="h-6 w-6 shrink-0 rounded-full border-2 border-zinc-700" />;
}

export default function ProgressTracker({
  steps,
}: {
  steps: Record<StepKey, StepStatus>;
}) {
  return (
    <ol className="mt-2">
      {STEP_META.map((meta, i) => {
        const status = steps[meta.key];
        const isLast = i === STEP_META.length - 1;
        return (
          <li key={meta.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <StepIcon status={status} />
              {!isLast && (
                <span
                  className={`my-1 w-px flex-1 ${
                    status === "done" ? "bg-emerald-600/40" : "bg-zinc-800"
                  }`}
                />
              )}
            </div>
            <div className={isLast ? "pb-1" : "pb-6"}>
              <div
                className={`text-sm font-medium ${
                  status === "pending" ? "text-zinc-500" : "text-zinc-100"
                }`}
              >
                {meta.label}
              </div>
              <div className="text-xs text-zinc-600">{meta.desc}</div>
              <div
                className={`mt-1 text-[11px] font-medium uppercase tracking-wide ${
                  status === "running"
                    ? "text-emerald-400"
                    : status === "done"
                      ? "text-emerald-600"
                      : "text-zinc-600"
                }`}
              >
                {STATUS_LABEL[status]}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
