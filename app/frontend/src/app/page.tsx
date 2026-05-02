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

export default function HomePage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const hasMessages = messages.length > 0;
  const placeholder = useMemo(
    () => (hasMessages ? "Ask follow-up about this research..." : "Type: Please research NVDA"),
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
    <div className="relative min-h-screen overflow-hidden bg-black text-zinc-100">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.06),transparent_40%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_10%,rgba(70,109,182,0.22),transparent_45%)]" />
      </div>

      <AppHeader />

      <main className="relative z-10 mx-auto flex h-[calc(100vh-88px)] w-full max-w-5xl flex-col px-6 pb-4">
        {!hasMessages ? (
          <section className="flex min-h-0 flex-1 flex-col items-center justify-center">
            <div className="mb-10 text-center">
              <p className="mb-3 text-xs uppercase tracking-[0.35em] text-zinc-500">
                Market Intelligence Workspace
              </p>
              <h1 className="text-5xl font-semibold tracking-tight text-white md:text-6xl">
                Veritake
              </h1>
            </div>
            <div className="w-full max-w-3xl">{composer}</div>
          </section>
        ) : (
          <>
            <section className="hide-scrollbar mx-auto min-h-0 w-full max-w-3xl flex-1 overflow-y-auto pb-4">
              <MessagesPane messages={messages} isLoading={isLoading} />
            </section>
            <section className="sticky bottom-0 mt-2 bg-linear-to-t from-black via-black/95 to-transparent pt-3">
              <div className="mx-auto w-full max-w-3xl">{composer}</div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
