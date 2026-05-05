"use client";

import { FormEvent, useMemo, useRef, useState } from "react";

import { MessagesPane } from "@/components/home/messages-pane";
import { FollowupMessage } from "@/components/home/workspace-types";
import { ChatMessage, ResearchFollowupResponse, ResearchResponse } from "@/components/home/types";
import { apiPost } from "@/lib/api/client";

type ReportTabProps = {
  runId: string;
  response?: ResearchResponse;
  formattedReport?: string;
  followup: FollowupMessage[];
  onAddFollowupMessage: (message: FollowupMessage) => void;
};

export function ReportTab({
  runId,
  response,
  formattedReport,
  followup,
  onAddFollowupMessage,
}: ReportTabProps) {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const reportMessage: ChatMessage = useMemo(
    () => ({
      id: `assistant-${runId}`,
      role: "assistant",
      content: formattedReport ?? "Report not available.",
    }),
    [formattedReport, runId],
  );

  const followupMessages: ChatMessage[] = useMemo(
    () =>
      followup.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
      })),
    [followup],
  );

  const combinedMessages = useMemo(
    () => [reportMessage, ...followupMessages],
    [followupMessages, reportMessage],
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = input.trim();
    if (!question || isSending) return;
    setInput("");
    setIsSending(true);

    const userMsg: FollowupMessage = {
      id: `followup-user-${Date.now()}`,
      role: "user",
      content: question,
      createdAt: Date.now(),
    };
    onAddFollowupMessage(userMsg);

    try {
      const payload = {
        question,
        company: response?.company ?? null,
        ticker: response?.ticker ?? null,
        brief: response?.brief,
        selected_evidence: response?.selected_evidence ?? [],
        chat_history: followupMessages.slice(-12).map((m) => ({ role: m.role, content: m.content })),
      };

      const result = await apiPost<ResearchFollowupResponse>("/research/followup", payload);
      const assistantMsg: FollowupMessage = {
        id: `followup-assistant-${Date.now()}`,
        role: "assistant",
        content: result.answer,
        createdAt: Date.now(),
      };
      onAddFollowupMessage(assistantMsg);
    } catch {
      const assistantMsg: FollowupMessage = {
        id: `followup-assistant-${Date.now()}`,
        role: "assistant",
        content: "I couldn't answer that follow-up right now. Please retry.",
        createdAt: Date.now(),
      };
      onAddFollowupMessage(assistantMsg);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  return (
    <section className="space-y-3">
      <section className="rounded-2xl border border-zinc-200 bg-zinc-100/60 p-4">
        <MessagesPane messages={combinedMessages} isLoading={isSending} />
      </section>
      <form onSubmit={onSubmit} className="relative w-full">
        <div className="relative rounded-2xl border border-zinc-200 bg-white px-5 py-3 shadow-[0_20px_45px_rgba(15,23,42,0.08)]">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={`Ask about this report...`}
                className="w-full bg-transparent text-sm text-zinc-900 placeholder:text-zinc-400 outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isSending || input.trim().length === 0}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              title="Send"
            >
              <svg
                aria-hidden
                viewBox="0 0 24 24"
                className="h-4 w-4 fill-none stroke-current"
                strokeWidth="2"
              >
                <path d="M12 17V7" />
                <path d="m7 12 5-5 5 5" />
              </svg>
            </button>
          </div>
        </div>
      </form>
    </section>
  );
}

