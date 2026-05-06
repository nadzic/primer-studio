export type ModelProvider = "openai" | "anthropic";

export type ModelOption = {
  id: string;
  label: string;
  provider: ModelProvider;
  model: string;
  hint?: string;
};

export const DEFAULT_MODEL_OPTION_ID = "openai:gpt-4o-mini";

export const MODEL_OPTIONS: ModelOption[] = [
  {
    id: "openai:gpt-4o-mini",
    label: "GPT-4o mini",
    provider: "openai",
    model: "gpt-4o-mini",
    hint: "Fast + cheap default",
  },
  {
    id: "openai:gpt-5.5",
    label: "GPT-5.5",
    provider: "openai",
    model: "gpt-5.5",
    hint: "Stronger reasoning",
  },
  {
    id: "anthropic:claude-4.6-sonnet",
    label: "Sonnet 4.6",
    provider: "anthropic",
    model: "claude-4.6-sonnet",
    hint: "Balanced",
  },
  {
    id: "anthropic:claude-4.7-opus",
    label: "Opus 4.7",
    provider: "anthropic",
    model: "claude-4.7-opus",
    hint: "Highest quality",
  },
];

export function getModelOption(id: string): ModelOption | null {
  return MODEL_OPTIONS.find((opt) => opt.id === id) ?? null;
}
