export function LoadingIndicator() {
  return (
    <div className="mb-5 flex justify-start">
      <article className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950/90 px-4 py-3">
        <div className="mb-2 inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          <span>Analyzing with agents</span>
        </div>
        <div className="space-y-1.5">
          <div className="h-2 w-full animate-pulse rounded bg-zinc-800" />
          <div className="h-2 w-5/6 animate-pulse rounded bg-zinc-800 [animation-delay:120ms]" />
          <div className="h-2 w-2/3 animate-pulse rounded bg-zinc-800 [animation-delay:240ms]" />
        </div>
        <div className="mt-3 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:0ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:120ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 [animation-delay:240ms]" />
        </div>
      </article>
    </div>
  );
}
