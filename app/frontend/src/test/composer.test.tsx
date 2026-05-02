import { type ComponentProps, createRef } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "../components/home/composer";

function renderComposer(overrides: Partial<ComponentProps<typeof Composer>> = {}) {
  const props: ComponentProps<typeof Composer> = {
    input: "",
    placeholder: "Ask about NVDA",
    inputRef: createRef<HTMLInputElement>(),
    onSubmit: vi.fn((event) => event.preventDefault()),
    onInputChange: vi.fn(),
    onInputFocus: vi.fn(),
    onInputBlur: vi.fn(),
    isDictating: false,
    isTranscribing: false,
    isDictationSupported: true,
    dictationDisabledReason: null,
    isLoading: false,
    onToggleDictation: vi.fn(),
    showSuggestions: false,
    visibleSuggestions: [],
    onSuggestionSelect: vi.fn(),
    ...overrides,
  };

  return render(<Composer {...props} />);
}

describe("Composer", () => {
  it("disables send button when input is empty and enables with text", () => {
    const initial = renderComposer({ input: "" });
    expect(screen.getByTitle("Send")).toBeDisabled();

    initial.unmount();
    renderComposer({ input: "Please analyze NVDA for swing trading" });
    expect(screen.getByTitle("Send")).toBeEnabled();
  });

  it("shows dictation disabled reason and disables dictation button", () => {
    renderComposer({
      dictationDisabledReason: "Microphone permission not granted.",
    });

    expect(screen.getByText("Microphone permission not granted.")).toBeInTheDocument();
    expect(screen.getByTitle("Microphone permission not granted.")).toBeDisabled();
  });

  it("renders suggestions and calls onSuggestionSelect on click", async () => {
    const user = userEvent.setup();
    const onSuggestionSelect = vi.fn();

    renderComposer({
      showSuggestions: true,
      visibleSuggestions: [
        "Please analyze NVDA for swing trading",
        "Please analyze AAPL for intraday trading",
      ],
      onSuggestionSelect,
    });

    await user.click(screen.getByText("Please analyze NVDA for swing trading"));
    expect(onSuggestionSelect).toHaveBeenCalledWith("Please analyze NVDA for swing trading");
  });
});
