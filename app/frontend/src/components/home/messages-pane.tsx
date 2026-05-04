import { LoadingIndicator } from "@/components/home/loading-indicator";
import { ChatMessage } from "@/components/home/types";

type MessagesPaneProps = {
  messages: ChatMessage[];
  isLoading: boolean;
};

export function MessagesPane({ messages, isLoading }: MessagesPaneProps) {
  return (
    <div className="px-1">
      {messages.map((message) => {
        const isUser = message.role === "user";
        return (
          <div key={message.id} className={`mb-5 flex ${isUser ? "justify-end" : "justify-start"}`}>
            <article
              className={`max-w-3xl whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                isUser
                  ? "bg-emerald-100 text-emerald-950"
                  : "border border-zinc-200 bg-white text-zinc-700"
              }`}
            >
              {message.content}
            </article>
          </div>
        );
      })}
      {isLoading && <LoadingIndicator />}
    </div>
  );
}
