export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type ResearchFollowupResponse = {
  answer: string;
  disclaimer: string;
};

export type Brief = {
  executive_summary: string | null;
  what_changed: BriefPoint[];
  what_matters_most_now: BriefPoint[];
  bull_points: BriefPoint[];
  bear_points: BriefPoint[];
  what_to_watch_next: BriefPoint[];
};

export type BriefPoint = {
  text: string;
  type: "fact" | "interpretation";
  evidence_strength: "strong" | "medium" | "weak" | null;
  source_url: string | null;
};

export type EvidenceQualitySummary = {
  strong: number;
  medium: number;
  weak: number;
};

export type TokenUsage = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type ResearchResponse = {
  company: string | null;
  ticker: string | null;
  brief: Brief;
  evidence_quality_summary: EvidenceQualitySummary;
  sources: Array<Record<string, unknown>>;
  selected_evidence: Array<Record<string, unknown>>;
  discarded_evidence_count: number;
  disclaimer: string;
  usage?: TokenUsage | null;
  warning: string | null;
  error: string | null;
};

export type TranscriptionResponse = {
  text: string;
};

export type ModelInfoResponse = {
  model: string;
};
