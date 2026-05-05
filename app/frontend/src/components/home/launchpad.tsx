"use client";

import { useEffect, useState } from "react";

import { ResearchRun } from "@/components/home/workspace-types";

const DEFAULT_STEPS = [
  "Understanding the company request",
  "Searching public web sources",
  "Ranking and filtering source quality",
  "Extracting evidence and classifying signals",
  "Synthesizing the final structured brief",
] as const;

function formatTime(ts: number): string {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function formatElapsed(elapsedMs: number): string {
  const elapsedSeconds = Math.max(0, elapsedMs) / 1000;
  if (elapsedSeconds < 60) return `${elapsedSeconds.toFixed(1)}s`;
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = elapsedSeconds - minutes * 60;
  return `${minutes}m ${seconds.toFixed(1)}s`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k tokens`;
  return `${tokens} tokens`;
}

function extractTopDomains(run: ResearchRun): string[] {
  const sources = run.response?.sources ?? [];
  const out: string[] = [];
  for (const source of sources) {
    const rawUrl =
      typeof source.url === "string" && source.url.trim()
        ? source.url.trim()
        : typeof source.source_url === "string" && source.source_url.trim()
          ? source.source_url.trim()
          : null;
    if (!rawUrl) continue;
    try {
      const host = new URL(rawUrl).hostname.replace(/^www\./, "");
      if (host && !out.includes(host)) out.push(host);
      if (out.length >= 4) break;
    } catch {
      continue;
    }
  }
  return out;
}

type LaunchpadProps = {
  runs: ResearchRun[];
  onOpenReport: (runId: string) => void;
};

export function Launchpad({ runs, onOpenReport }: LaunchpadProps) {
  const sorted = [...runs].sort((a, b) => b.createdAt - a.createdAt);
  const runningRun = sorted.find((run) => run.status === "running") ?? null;
  const runningRunId = runningRun?.id ?? null;
  const runningRunCreatedAt = runningRun?.createdAt ?? null;

  // One shared timer that powers progress for the currently running run.
  const [runningElapsedMs, setRunningElapsedMs] = useState(0);
  useEffect(() => {
    if (!runningRunId || !runningRunCreatedAt) return;
    const startedAt = runningRunCreatedAt;
    const interval = window.setInterval(() => {
      setRunningElapsedMs(Date.now() - startedAt);
    }, 400);
    return () => window.clearInterval(interval);
  }, [runningRunId, runningRunCreatedAt]);

  return (
    <section className="mx-auto w-full max-w-4xl space-y-4">
      <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-3">
        <p className="text-sm text-zinc-600">
          Structured output for the technical task: facts first, interpretation second.
        </p>
      </div>

      {sorted.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 bg-white p-8 text-center">
          <p className="text-sm text-zinc-600">
            No research runs yet. Start by querying a company or ticker.
          </p>
        </div>
      ) : (
        <>
          <section className="rounded-2xl border border-zinc-200 bg-white p-4">
            <header className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-900">Search history</h3>
              <p className="text-xs text-zinc-500">{sorted.length} runs</p>
            </header>
            <div className="space-y-2">
              {sorted.map((run) => {
                const label =
                  run.response?.ticker && run.response?.company
                    ? `${run.response.company} (${run.response.ticker})`
                    : run.query;
                const domains = extractTopDomains(run);
                const steps =
                  run.response?.brief &&
                  "workflow_trace" in run.response.brief &&
                  Array.isArray((run.response.brief as Record<string, unknown>).workflow_trace)
                    ? ((run.response.brief as Record<string, unknown>).workflow_trace as string[])
                    : [...DEFAULT_STEPS];
                const stepsCount = steps.length;
                const isRunning = run.status === "running";
                const resolvedElapsedMs =
                  isRunning && run.id === runningRunId
                    ? runningElapsedMs
                    : run.finishedAt
                      ? run.finishedAt - run.createdAt
                      : 0;
                const estimatedTokens = Math.round(
                  isRunning && run.id === runningRunId
                    ? Math.max(1200, (resolvedElapsedMs / 1000) * 550)
                    : Math.max(1200, stepsCount * 1200),
                );
                const activeStepIndex = isRunning
                  ? Math.min(Math.floor(resolvedElapsedMs / 4_500), Math.max(stepsCount - 1, 0))
                  : Math.max(stepsCount - 1, 0);
                const completedSteps = run.status === "completed" ? stepsCount : activeStepIndex + 1;
                return (
                  <article
                    key={run.id}
                    className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{label}</p>
                        <p className="text-xs text-zinc-500">{formatTime(run.createdAt)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[11px] ${
                            run.status === "running"
                              ? "border-amber-200 bg-amber-50 text-amber-900"
                              : run.status === "completed"
                                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                                : "border-red-200 bg-red-50 text-red-900"
                          }`}
                        >
                          {run.status}
                        </span>
                        <button
                          type="button"
                          onClick={() => onOpenReport(run.id)}
                          disabled={run.status !== "completed"}
                          className="rounded-full bg-zinc-900 px-3 py-1 text-xs font-medium text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Open tab
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {domains.length > 0 ? (
                        domains.map((domain) => (
                          <span
                            key={`${run.id}-${domain}`}
                            className="rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-600"
                          >
                            {domain}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-zinc-500">No source domains yet.</span>
                      )}
                    </div>

                    <div className="mt-3 rounded-xl border border-zinc-200 bg-white px-3 py-2">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-zinc-500">
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              isRunning ? "animate-pulse bg-emerald-400" : "bg-emerald-500"
                            }`}
                          />
                          <span>Analyzing with agents</span>
                        </div>
                        <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] text-zinc-600">
                          {Math.min(completedSteps, stepsCount)}/{stepsCount} steps
                        </span>
                        <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] text-zinc-600">
                          {formatElapsed(resolvedElapsedMs)}
                        </span>
                        <span className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[11px] text-zinc-600">
                          {formatTokens(estimatedTokens)}
                        </span>
                      </div>

                      {isRunning ? (
                        <div className="space-y-2">
                          {steps.map((step, index) => {
                            const isDone = index < activeStepIndex;
                            const isActive = index === activeStepIndex;
                            return (
                              <div key={`${run.id}-${step}`} className="flex items-center gap-2">
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
                      ) : (
                        <details className="text-sm text-zinc-700">
                          <summary className="cursor-pointer select-none text-xs font-medium text-zinc-600">
                            Workflow trace
                          </summary>
                          <ul className="mt-2 space-y-1 text-sm text-zinc-700">
                            {steps.slice(0, 8).map((step, idx) => (
                              <li key={`${run.id}-trace-${idx}`} className="flex gap-2">
                                <span className="mt-[0.35rem] h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400" />
                                <span>{step}</span>
                              </li>
                            ))}
                          </ul>
                          {run.status === "failed" && run.errorMessage && (
                            <p className="mt-2 text-xs text-red-700">{run.errorMessage}</p>
                          )}
                        </details>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </>
      )}
    </section>
  );
}

