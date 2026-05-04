import { ReactNode } from "react";

import { LoadingIndicator } from "@/components/home/loading-indicator";
import { ChatMessage } from "@/components/home/types";

type MessagesPaneProps = {
  messages: ChatMessage[];
  isLoading: boolean;
};

const SECTION_TITLES = new Set([
  "latest reporting research brief",
  "executive summary",
  "what changed",
  "what matters most now",
  "bull points",
  "bear points",
  "what to watch next",
  "evidence quality",
  "sources used",
  "disclaimer",
  "warning",
  "error",
]);

function isSectionTitleLine(line: string): boolean {
  const normalized = line.trim().replace(/[:\s]+$/g, "").toLowerCase();
  return SECTION_TITLES.has(normalized);
}

function renderInlineContent(text: string): ReactNode[] {
  const markdownLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  const chunks: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = markdownLinkRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      chunks.push(...renderInlineContentWithoutMarkdownLinks(text.slice(lastIndex, match.index)));
    }
    const [, label, href] = match;
    chunks.push(
      <a
        key={`md-link-${match.index}-${href}`}
        href={href}
        target="_blank"
        rel="noreferrer noopener"
        className="text-emerald-700 underline decoration-emerald-400 underline-offset-2 hover:text-emerald-800"
      >
        {label}
      </a>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    chunks.push(...renderInlineContentWithoutMarkdownLinks(text.slice(lastIndex)));
  }
  return chunks;
}

function renderInlineContentWithoutMarkdownLinks(text: string): ReactNode[] {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const chunks: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = urlRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      chunks.push(...renderBoldSegments(text.slice(lastIndex, match.index), `text-${match.index}`));
    }

    const rawUrl = match[0];
    const trimmedUrl = rawUrl.replace(/[),.;!?]+$/g, "");
    const suffix = rawUrl.slice(trimmedUrl.length);
    chunks.push(
      <a
        key={`url-${match.index}-${trimmedUrl}`}
        href={trimmedUrl}
        target="_blank"
        rel="noreferrer noopener"
        className="text-emerald-700 underline decoration-emerald-400 underline-offset-2 hover:text-emerald-800"
      >
        {trimmedUrl}
      </a>,
    );
    if (suffix) chunks.push(suffix);
    lastIndex = match.index + rawUrl.length;
  }

  if (lastIndex < text.length) {
    chunks.push(...renderBoldSegments(text.slice(lastIndex), `tail-${lastIndex}`));
  }
  return chunks;
}

function renderBoldSegments(text: string, keyPrefix: string): ReactNode[] {
  const boldRegex = /\*\*([^*]+)\*\*/g;
  const chunks: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = boldRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      chunks.push(text.slice(lastIndex, match.index));
    }
    chunks.push(
      <strong key={`${keyPrefix}-bold-${match.index}`} className="font-semibold text-zinc-900">
        {match[1]}
      </strong>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    chunks.push(text.slice(lastIndex));
  }
  return chunks;
}

function renderAssistantLine(line: string, index: number): ReactNode {
  if (!line.trim()) {
    return <div key={`line-${index}`} className="h-2" />;
  }

  if (line.startsWith("### ")) {
    return (
      <h4 key={`line-${index}`} className="mt-2 text-sm font-semibold text-zinc-900">
        {renderInlineContent(line.slice(4))}
      </h4>
    );
  }

  if (line.startsWith("## ")) {
    return (
      <h3 key={`line-${index}`} className="text-base font-semibold text-zinc-900">
        {renderInlineContent(line.slice(3))}
      </h3>
    );
  }

  if (line.startsWith("# ")) {
    return (
      <h2 key={`line-${index}`} className="text-lg font-semibold text-zinc-900">
        {renderInlineContent(line.slice(2))}
      </h2>
    );
  }

  if (line.startsWith("- ")) {
    return (
      <div key={`line-${index}`} className="flex gap-2 pl-1">
        <span className="mt-[0.4rem] h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400" />
        <p className="min-w-0">{renderInlineContent(line.slice(2))}</p>
      </div>
    );
  }

  if (isSectionTitleLine(line)) {
    return (
      <h4 key={`line-${index}`} className="mt-2 font-semibold text-zinc-900">
        {renderInlineContent(line)}
      </h4>
    );
  }

  return (
    <p key={`line-${index}`} className="text-zinc-700">
      {renderInlineContent(line)}
    </p>
  );
}

function AssistantMessage({ content }: { content: string }) {
  const lines = content.split("\n");
  return <div className="space-y-1.5">{lines.map((line, index) => renderAssistantLine(line, index))}</div>;
}

export function MessagesPane({ messages, isLoading }: MessagesPaneProps) {
  return (
    <div className="px-1">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <div key={message.id} className={`mb-5 flex ${isUser ? "justify-end" : "justify-start"}`}>
            <article
              className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                isUser
                  ? "bg-emerald-100 text-emerald-950"
                  : "border border-zinc-200 bg-white text-zinc-700"
              }`}
            >
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <AssistantMessage content={message.content} />
              )}
            </article>
          </div>
        );
      })}
      {isLoading && <LoadingIndicator />}
    </div>
  );
}
