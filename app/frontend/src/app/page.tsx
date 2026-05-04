"use client";

import { FormEvent, useMemo, useRef, useState } from "react";

import { ANALYZE_TIMEOUT_MS } from "@/components/home/constants";
import { AppHeader } from "@/components/home/app-header";
import { Composer } from "@/components/home/composer";
import { MessagesPane } from "@/components/home/messages-pane";
import { ChatMessage, ResearchResponse } from "@/components/home/types";
import {
  formatResearchReply,
  getAnalyzeErrorMessage,
  getVisibleSuggestions,
} from "@/components/home/utils";
import { apiPost } from "@/lib/api/client";

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

export default function HomePage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const hasMessages = messages.length > 0;
  const placeholder = useMemo(
    () =>
      hasMessages
        ? "Ask follow-up about this research..."
        : "Type: Research AAPL latest reporting changes",
    [hasMessages],
  );
  const visibleSuggestions = useMemo(() => getVisibleSuggestions(input), [input]);
  const showSuggestions =
    !hasMessages && isInputFocused && !isLoading && visibleSuggestions.length > 0;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = input.trim();
    if (!query || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const assistantMessageId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "Researching latest reporting...",
      },
    ]);

    const abortController = new AbortController();
    const timeoutId = window.setTimeout(() => {
      abortController.abort();
    }, ANALYZE_TIMEOUT_MS);

    try {
      const response = await apiPost<ResearchResponse>(
        "/research",
        { query },
        { signal: abortController.signal },
      );
      const formatted = formatResearchReply(response);
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantMessageId ? { ...message, content: formatted } : message,
        ),
      );
    } catch (error) {
      const text = getAnalyzeErrorMessage(error, ANALYZE_TIMEOUT_MS);
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: `I could not complete the research.\n\n${text}`,
              }
            : message,
        ),
      );
    } finally {
      window.clearTimeout(timeoutId);
      setIsLoading(false);
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
      isLoading={isLoading}
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

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-8 md:px-8">
        {!hasMessages ? (
          <>
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

            <section className="mx-auto mb-20 w-full max-w-4xl rounded-3xl border border-zinc-200 bg-white p-6 shadow-[0_25px_60px_rgba(15,23,42,0.06)] md:p-8">
              <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">
                Try the workflow
              </h2>
              <p className="mt-2 text-sm text-zinc-600">
                Enter a company or ticker and get a structured brief: what changed, what matters,
                bull vs bear points, and what to watch next.
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
          </>
        ) : (
          <section className="mx-auto flex min-h-[calc(100vh-150px)] w-full max-w-4xl flex-col">
            <div className="mb-4 rounded-2xl border border-zinc-200 bg-white px-4 py-3">
              <p className="text-sm text-zinc-600">
                Structured output for the technical task: facts first, interpretation second.
              </p>
            </div>
            <section className="hide-scrollbar min-h-0 flex-1 overflow-y-auto rounded-2xl border border-zinc-200 bg-zinc-100/60 p-4">
              <MessagesPane messages={messages} isLoading={isLoading} />
            </section>
            <section className="sticky bottom-4 mt-4 rounded-2xl bg-zinc-50/95 p-1 backdrop-blur">
              <div>{composer}</div>
            </section>
          </section>
        )}
      </main>
    </div>
  );
}
