import { useEffect, useMemo, useState } from "react";

const AGENT_FLOW_STEPS = [
  "Understanding the company request",
  "Searching public web sources",
  "Ranking and filtering source quality",
  "Extracting evidence and classifying signals",
  "Synthesizing the final structured brief",
] as const;

function formatElapsed(elapsedMs: number): string {
  const elapsedSeconds = elapsedMs / 1000;
  if (elapsedSeconds < 60) {
    return `${elapsedSeconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds - minutes * 60;
  return `${minutes}m ${seconds.toFixed(1)}s`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k tokens`;
  return `${tokens} tokens`;
}

export function LoadingIndicator() {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 400);
    return () => window.clearInterval(interval);
  }, []);

  const activeStepIndex = useMemo(() => {
    const stepDurationMs = 4_500;
    const rawIndex = Math.floor(elapsedMs / stepDurationMs);
    return Math.min(rawIndex, AGENT_FLOW_STEPS.length - 1);
  }, [elapsedMs]);
  const completedSteps = Math.min(activeStepIndex + 1, AGENT_FLOW_STEPS.length);
  const estimatedTokens = Math.round(Math.max(1_200, (elapsedMs / 1000) * 550));

  return (
    <div className="mb-5 flex justify-start">
      <article className="w-full max-w-3xl rounded-2xl border border-zinc-200 bg-white px-4 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
            <span>Analyzing with agents</span>
          </div>
          <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600">
            {completedSteps}/{AGENT_FLOW_STEPS.length} steps
          </span>
          <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600">
            {formatElapsed(elapsedMs)}
          </span>
          <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs text-zinc-600">
            {formatTokens(estimatedTokens)}
          </span>
        </div>
        <p className="mb-3 text-xs text-zinc-500">Workflow progress</p>
        <div className="space-y-2.5">
          {AGENT_FLOW_STEPS.map((step, index) => {
            const isDone = index < activeStepIndex;
            const isActive = index === activeStepIndex;
            return (
              <div key={step} className="flex items-center gap-2">
                <span
                  className={`inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px] ${
                    isDone
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : isActive
                        ? "border-emerald-400 bg-emerald-50 text-emerald-700"
                        : "border-zinc-300 bg-white text-zinc-400"
                  }`}
                >
                  {isDone ? "✓" : index + 1}
                </span>
                <span className={isActive ? "text-sm text-zinc-900" : "text-sm text-zinc-500"}>
                  {step}
                </span>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:0ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:120ms]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:240ms]" />
        </div>
      </article>
    </div>
  );
}
