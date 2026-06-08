// Placeholder shown in the report panel while the pipeline runs.
export default function SkeletonLoader() {
  return (
    <div className="animate-pulse space-y-8" aria-hidden>
      {/* Title */}
      <div className="space-y-3">
        <div className="h-8 w-2/3 rounded bg-zinc-800" />
        <div className="h-4 w-1/3 rounded bg-zinc-800/70" />
      </div>

      {/* Executive summary lines */}
      <div className="space-y-3">
        <div className="h-4 w-full rounded bg-zinc-800/70" />
        <div className="h-4 w-11/12 rounded bg-zinc-800/70" />
        <div className="h-4 w-4/5 rounded bg-zinc-800/70" />
      </div>

      {/* Section divider + heading */}
      <div className="h-px w-full bg-zinc-800" />
      <div className="h-5 w-1/4 rounded bg-zinc-800" />

      {/* Financial table block */}
      <div className="space-y-2 rounded-lg border border-zinc-800 p-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-2/5 rounded bg-zinc-800/70" />
            <div className="h-4 w-1/5 rounded bg-zinc-800/50" />
          </div>
        ))}
      </div>

      {/* More text */}
      <div className="space-y-3">
        <div className="h-4 w-full rounded bg-zinc-800/70" />
        <div className="h-4 w-10/12 rounded bg-zinc-800/70" />
        <div className="h-4 w-9/12 rounded bg-zinc-800/70" />
      </div>
    </div>
  );
}
