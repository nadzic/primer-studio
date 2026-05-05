"use client";

import { FormEvent, useMemo, useRef, useState } from "react";

import { ANALYZE_TIMEOUT_MS } from "@/components/home/constants";
import { AppHeader } from "@/components/home/app-header";
import { Composer } from "@/components/home/composer";
import { Launchpad } from "@/components/home/launchpad";
import { ReportTab } from "@/components/home/report-tab";
import { TabsBar } from "@/components/home/tabs-bar";
import { ResearchResponse } from "@/components/home/types";
import {
  formatResearchReply,
  getAnalyzeErrorMessage,
  getVisibleSuggestions,
} from "@/components/home/utils";
import { ResearchRun, WorkspaceTab } from "@/components/home/workspace-types";
import { API_BASE_URL, apiPost } from "@/lib/api/client";

type FeatureSection = {
  eyebrow: string;
  title: string;
  description: string;
  chips: string[];
  reverse?: boolean;
};

const FEATURE_SECTIONS: FeatureSection[] = [
  {
    eyebrow: "Living model",
    title: "Research that compounds.",
    description:
      "Every assumption, note, and piece of reasoning is saved. Your research workflow improves every quarter instead of restarting from scratch.",
    chips: ["Your Methodology", "Context Preserved", "No More Rebuilds", "Improves Over Time"],
  },
  {
    eyebrow: "Scalability",
    title: "Depth that scales.",
    description:
      "Run retrieval, ranking, and synthesis in one flow. The output stays concise, but the supporting evidence expands with each cycle.",
    chips: ["Analyst-Level Depth", "Accurate Retrieval", "Broadens Coverage", "Scalable Process"],
    reverse: true,
  },
  {
    eyebrow: "Always-on research",
    title: "Reports, delivered.",
    description:
      "Upload coverage and receive preview notes ahead of earnings. Briefings are assembled automatically and easy to scan.",
    chips: ["Earnings Previews", "Read-Across", "Earnings Briefings", "Auto-delivered"],
  },
];

function FeatureChips({ chips }: { chips: string[] }) {
  return (
    <div className="mt-8 flex flex-wrap gap-3">
      {chips.map((chip) => (
        <span
          key={chip}
          className="inline-flex rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700"
        >
          {chip}
        </span>
      ))}
    </div>
  );
}

function ProductPreview({ muted = false }: { muted?: boolean }) {
  return (
    <div
      className={`overflow-hidden rounded-3xl border border-zinc-200 ${
        muted ? "bg-zinc-50" : "bg-emerald-50/60"
      }`}
    >
      <div className="grid gap-4 p-5 md:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-zinc-200 bg-white p-3">
          <div className="mb-3 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-200" />
          </div>
          <div className="space-y-2">
            {Array.from({ length: 7 }).map((_, index) => (
              <div
                // A dense table-like rhythm to mimic the Primer workspace visual.
                key={`row-${index}`}
                className="grid grid-cols-4 gap-2"
              >
                <span className="h-2 rounded bg-zinc-200" />
                <span className="h-2 rounded bg-zinc-200" />
                <span className="h-2 rounded bg-zinc-200" />
                <span className="h-2 rounded bg-zinc-200" />
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2 text-[11px] font-medium text-zinc-500">
            <span className="rounded-full bg-zinc-100 px-2 py-1">Model</span>
            <span className="rounded-full bg-zinc-100 px-2 py-1">Charts</span>
            <span className="rounded-full bg-zinc-100 px-2 py-1">Notes</span>
            <span className="rounded-full bg-zinc-100 px-2 py-1">Comments</span>
          </div>
        </div>
        <div className="rounded-2xl border border-zinc-200 bg-white p-3">
          <div className="mb-3 h-2.5 w-20 rounded bg-zinc-200" />
          <div className="space-y-2">
            <div className="rounded-lg border border-zinc-200 p-2">
              <div className="mb-2 h-2 w-full rounded bg-zinc-200" />
              <div className="h-2 w-5/6 rounded bg-zinc-200" />
            </div>
            <div className="rounded-lg border border-zinc-200 p-2">
              <div className="mb-2 h-2 w-full rounded bg-zinc-200" />
              <div className="h-2 w-2/3 rounded bg-zinc-200" />
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-zinc-200 bg-zinc-50 p-2">
            <div className="mb-2 h-2 w-16 rounded bg-zinc-200" />
            <div className="h-2 w-full rounded bg-zinc-200" />
          </div>
        </div>
      </div>
    </div>
  );
}

function createRunId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `run-${crypto.randomUUID()}`;
  }
  return `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getReportTabTitle(response: ResearchResponse | undefined, query: string): string {
  const ticker = response?.ticker?.trim();
  const company = response?.company?.trim();
  if (ticker) return `${ticker} Research`;
  if (company) return `${company} Research`;
  const fallback = query.trim().slice(0, 24);
  return `${fallback || "Stock"} Research`;
}

async function assertBackendReachable(): Promise<void> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 5_000);
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Health check returned ${response.status}`);
    }
  } catch (error) {
    const reason =
      error instanceof Error && error.message ? error.message : "unreachable backend";
    throw new Error(
      `Backend is not reachable at ${API_BASE_URL} (${reason}). Start the API server and retry.`,
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export default function HomePage() {
  const [input, setInput] = useState("");
  const [isInputFocused, setIsInputFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const [runs, setRuns] = useState<ResearchRun[]>([]);
  const [tabs, setTabs] = useState<WorkspaceTab[]>([
    { id: "tab-launchpad", kind: "launchpad", title: "Launchpad" },
  ]);
  const [activeTabId, setActiveTabId] = useState("tab-launchpad");

  const hasWorkspace = runs.length > 0 || tabs.length > 1;
  const placeholder = useMemo(
    () => (hasWorkspace ? "Research another company..." : "Type: Research AAPL latest reporting changes"),
    [hasWorkspace],
  );
  const visibleSuggestions = useMemo(() => getVisibleSuggestions(input), [input]);
  const showSuggestions = !hasWorkspace && isInputFocused && visibleSuggestions.length > 0;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = input.trim();
    if (!query) return;

    setInput("");
    setActiveTabId("tab-launchpad");
    const runId = createRunId();
    const createdAt = Date.now();
    setRuns((prev) => [
      ...prev,
      {
        id: runId,
        query,
        createdAt,
        status: "running",
        followup: [],
      },
    ]);

    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      abortController.abort();
      setRuns((prev) =>
        prev.map((run) =>
          run.id === runId && run.status === "running"
            ? {
                ...run,
                status: "failed",
                finishedAt: Date.now(),
                errorMessage: `Request timed out after ${Math.round(ANALYZE_TIMEOUT_MS / 1000)}s`,
              }
            : run,
        ),
      );
    }, ANALYZE_TIMEOUT_MS);

    try {
      await assertBackendReachable();
      const response = await apiPost<ResearchResponse>(
        "/research",
        { query },
        { signal: abortController.signal },
      );
      const formatted = formatResearchReply(response);
      setRuns((prev) =>
        prev.map((run) =>
          run.id === runId
            ? {
                ...run,
                status: "completed",
                finishedAt: Date.now(),
                response,
                formattedReport: formatted,
              }
            : run,
        ),
      );

      const title = getReportTabTitle(response, query);
      const reportTabId = `tab-report-${runId}`;
      setTabs((prev) => {
        const existing = prev.find((tab) => tab.kind === "report" && tab.runId === runId);
        if (existing) return prev;
        return [...prev, { id: reportTabId, kind: "report", title, runId }];
      });
      setActiveTabId(reportTabId);
    } catch (error) {
      const text = getAnalyzeErrorMessage(error, ANALYZE_TIMEOUT_MS);
      setRuns((prev) =>
        prev.map((run) =>
          run.id === runId
            ? {
                ...run,
                status: "failed",
                finishedAt: Date.now(),
                errorMessage: text,
              }
            : run,
        ),
      );
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  const composer = (
    <Composer
      input={input}
      placeholder={placeholder}
      inputRef={inputRef}
      onSubmit={onSubmit}
      onInputChange={setInput}
      onInputFocus={() => setIsInputFocused(true)}
      onInputBlur={() => setIsInputFocused(false)}
      isDictating={false}
      isTranscribing={false}
      isDictationSupported={false}
      dictationDisabledReason={null}
      isLoading={false}
      onToggleDictation={() => undefined}
      showSuggestions={showSuggestions}
      visibleSuggestions={visibleSuggestions}
      onSuggestionSelect={(prompt) => {
        setInput(prompt);
        setIsInputFocused(false);
        inputRef.current?.focus();
      }}
      showDictation={false}
    />
  );

  function closeTab(tabId: string) {
    setTabs((prev) => prev.filter((tab) => tab.id !== tabId));
    setActiveTabId((prevActive) => {
      if (prevActive !== tabId) return prevActive;
      return "tab-launchpad";
    });
  }

  function openReportForRun(runId: string) {
    const run = runs.find((item) => item.id === runId);
    if (!run || run.status !== "completed") return;
    const tabId = `tab-report-${runId}`;
    setTabs((prev) => {
      const existing = prev.find((tab) => tab.id === tabId);
      if (existing) return prev;
      const title = getReportTabTitle(run.response, run.query);
      return [...prev, { id: tabId, kind: "report", title, runId }];
    });
    setActiveTabId(tabId);
  }

  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? tabs[0];
  const activeRun =
    activeTab.kind === "report" ? runs.find((run) => run.id === activeTab.runId) : undefined;

  if (hasWorkspace) {
    return (
      <div className="h-screen overflow-hidden bg-zinc-50 text-zinc-900">
        <AppHeader />
        <div className="fixed inset-x-0 bottom-0 top-16">
          <div className="mx-auto flex h-full w-full max-w-4xl flex-col px-6 md:px-8">
            <div className="shrink-0 pt-4">
              <TabsBar
                tabs={tabs}
                activeTabId={activeTabId}
                onSelect={setActiveTabId}
                onClose={closeTab}
                onCreateNew={() => {
                  setActiveTabId("tab-launchpad");
                  inputRef.current?.focus();
                }}
              />
            </div>

            <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto pb-4">
              {activeTab.kind === "launchpad" ? (
                <Launchpad runs={runs} onOpenReport={openReportForRun} />
              ) : (
                <ReportTab
                  runId={activeTab.runId}
                  response={activeRun?.response}
                  formattedReport={activeRun?.formattedReport}
                  followup={activeRun?.followup ?? []}
                  onAddFollowupMessage={(message) => {
                    setRuns((prev) =>
                      prev.map((run) =>
                        run.id === activeTab.runId
                          ? { ...run, followup: [...run.followup, message] }
                          : run,
                      ),
                    );
                  }}
                />
              )}
            </div>

            {activeTab.kind === "launchpad" && (
              <div className="shrink-0 pb-4 pt-2">
                <div className="rounded-2xl bg-zinc-50/95 p-1 backdrop-blur">
                  <div>{composer}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-24 md:px-8">
        <section className="mx-auto mb-20 max-w-4xl text-center">
          <p className="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-emerald-700">
            Agentic Equity Research
          </p>
          <h1 className="text-5xl font-semibold tracking-tight text-zinc-900 md:text-7xl">
            The AI equity analyst
          </h1>
          <p className="mx-auto mt-5 max-w-3xl text-lg leading-relaxed text-zinc-600">
            Build a retail-investor workflow that finds what changed, ranks source quality, and
            clearly separates evidence from interpretation.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              className="rounded-full bg-emerald-300 px-6 py-3 text-sm font-semibold text-zinc-900"
            >
              See features
            </button>
          </div>
          <div className="mt-12">
            <ProductPreview />
          </div>
        </section>

        <section className="mx-auto mb-20 w-full max-w-4xl rounded-3xl border-2 border-emerald-300/80 bg-white p-6 shadow-[0_25px_60px_rgba(15,23,42,0.06)] md:p-8">
          <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">Try the workflow</h2>
          <p className="mt-2 text-sm text-zinc-600">
            Enter a company or ticker and get a structured brief: what changed, what matters, bull
            vs bear points, and what to watch next.
          </p>
          <div className="mt-6">{composer}</div>
        </section>

        <section className="space-y-16">
          {FEATURE_SECTIONS.map((section) => (
            <article
              key={section.title}
              className="grid items-center gap-10 rounded-3xl border border-zinc-200 bg-zinc-50/80 p-6 md:grid-cols-2 md:p-8"
            >
              <div className={section.reverse ? "md:order-2" : undefined}>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                  {section.eyebrow}
                </p>
                <h3 className="mt-3 text-4xl font-semibold tracking-tight text-zinc-900 md:text-5xl">
                  {section.title}
                </h3>
                <p className="mt-5 max-w-lg text-lg leading-relaxed text-zinc-600">
                  {section.description}
                </p>
                <FeatureChips chips={section.chips} />
              </div>
              <div className={section.reverse ? "md:order-1" : undefined}>
                <ProductPreview muted />
              </div>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
