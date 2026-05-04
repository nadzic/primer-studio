import { FormEvent, RefObject } from "react";

type ComposerProps = {
  input: string;
  placeholder: string;
  inputRef: RefObject<HTMLInputElement | null>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onInputChange: (value: string) => void;
  onInputFocus: () => void;
  onInputBlur: () => void;
  isDictating: boolean;
  isTranscribing: boolean;
  isDictationSupported: boolean;
  dictationDisabledReason: string | null;
  isLoading: boolean;
  onToggleDictation: () => void;
  showSuggestions: boolean;
  visibleSuggestions: string[];
  onSuggestionSelect: (prompt: string) => void;
  showDictation?: boolean;
};

export function Composer({
  input,
  placeholder,
  inputRef,
  onSubmit,
  onInputChange,
  onInputFocus,
  onInputBlur,
  isDictating,
  isTranscribing,
  isDictationSupported,
  dictationDisabledReason,
  isLoading,
  onToggleDictation,
  showSuggestions,
  visibleSuggestions,
  onSuggestionSelect,
  showDictation = true,
}: ComposerProps) {
  return (
    <form onSubmit={onSubmit} className="relative w-full">
      <div className="relative rounded-2xl border border-zinc-200 bg-white px-5 py-3 shadow-[0_20px_45px_rgba(15,23,42,0.08)]">
        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(event) => onInputChange(event.target.value)}
                onFocus={onInputFocus}
                onBlur={onInputBlur}
                placeholder={placeholder}
                className="w-full bg-transparent text-sm text-zinc-900 placeholder:text-zinc-400 outline-none"
              />
            </div>
            {showDictation && (
              <button
                type="button"
                onClick={onToggleDictation}
                disabled={
                  isLoading ||
                  isTranscribing ||
                  !isDictationSupported ||
                  Boolean(dictationDisabledReason)
                }
                title={
                  dictationDisabledReason ??
                  (isTranscribing
                    ? "Transcribing..."
                    : isDictating
                      ? "Stop dictation"
                      : "Dictation")
                }
                className={`inline-flex h-9 w-9 items-center justify-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  isDictating
                    ? "border-red-400 bg-red-100 text-red-700"
                    : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                {isDictating ? (
                  <span className="h-2.5 w-2.5 rounded-[2px] bg-current" />
                ) : (
                  <svg
                    aria-hidden
                    viewBox="0 0 24 24"
                    className="h-4 w-4 fill-none stroke-current"
                    strokeWidth="1.8"
                  >
                    <path d="M12 4a3 3 0 0 1 3 3v5a3 3 0 1 1-6 0V7a3 3 0 0 1 3-3Z" />
                    <path d="M5 11.5a7 7 0 0 0 14 0" />
                    <path d="M12 18.5v2.5" />
                  </svg>
                )}
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading || input.trim().length === 0}
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
        {dictationDisabledReason && (
          <p className="mt-2 text-xs text-amber-700">{dictationDisabledReason}</p>
        )}
        {showSuggestions && (
          <div className="absolute top-full left-0 z-30 mt-2 w-full overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl">
            {visibleSuggestions.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => onSuggestionSelect(prompt)}
                className="flex w-full items-center gap-3 border-b border-zinc-100 px-4 py-2.5 text-left text-sm text-zinc-600 transition last:border-b-0 hover:bg-zinc-50 hover:text-zinc-900"
              >
                <svg
                  aria-hidden
                  viewBox="0 0 24 24"
                  className="h-4 w-4 shrink-0 fill-none stroke-zinc-400"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
                <span>{prompt}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </form>
  );
}
