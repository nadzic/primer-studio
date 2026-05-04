const DEFAULT_ANALYZE_TIMEOUT_MS = 180_000;
const MIN_ANALYZE_TIMEOUT_MS = 10_000;
const MAX_ANALYZE_TIMEOUT_MS = 600_000;

function parseAnalyzeTimeoutMs(rawValue: string | undefined): number {
  if (!rawValue) return DEFAULT_ANALYZE_TIMEOUT_MS;
  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed)) return DEFAULT_ANALYZE_TIMEOUT_MS;
  return Math.min(Math.max(parsed, MIN_ANALYZE_TIMEOUT_MS), MAX_ANALYZE_TIMEOUT_MS);
}

export const ANALYZE_TIMEOUT_MS = parseAnalyzeTimeoutMs(
  process.env.NEXT_PUBLIC_RESEARCH_TIMEOUT_MS,
);

export const SUGGESTED_PROMPTS = [
  "Please research NVDA",
  "Please research AAPL and explain what changed in latest reporting",
  "Please research TSLA and list bull and bear points",
] as const;
