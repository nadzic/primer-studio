import { SUGGESTED_PROMPTS } from "@/components/home/constants";
import { BriefPoint, ResearchResponse } from "@/components/home/types";

function formatBriefPoint(point: BriefPoint): string {
  const kind = point.type === "fact" ? "FACT" : "INTERPRETATION";
  const strength = point.evidence_strength ?? "unknown";
  const source = point.source_url ? ` ([source](${point.source_url}))` : "";
  return `**[${kind} | ${strength}]** ${point.text}${source}`;
}

function formatSection(title: string, items: BriefPoint[], emptyMessage = "No items extracted."): string[] {
  if (items.length === 0) {
    return [`### ${title}`, `- ${emptyMessage}`];
  }
  return [`### ${title}`, ...items.map((item) => `- ${formatBriefPoint(item)}`)];
}

function formatSource(source: Record<string, unknown>, index: number): string {
  const title =
    typeof source.title === "string" && source.title.trim() ? source.title.trim() : "Source";
  const sourceType =
    typeof source.source_type === "string" && source.source_type.trim()
      ? source.source_type.trim()
      : "unknown";
  const score =
    typeof source.final_source_score === "number" && Number.isFinite(source.final_source_score)
      ? source.final_source_score.toFixed(2)
      : "n/a";
  const sourceUrl =
    typeof source.url === "string" && source.url.trim()
      ? source.url.trim()
      : typeof source.source_url === "string" && source.source_url.trim()
        ? source.source_url.trim()
        : null;
  const titleText = sourceUrl ? `[${index + 1}. ${title}](${sourceUrl})` : `${index + 1}. ${title}`;
  return `- ${titleText} - ${sourceType} - score ${score}`;
}

export function formatResearchReply(payload: ResearchResponse): string {
  const company = payload.company || "Unknown company";
  const ticker = payload.ticker || "N/A";
  const brief = payload.brief;
  const quality = payload.evidence_quality_summary;
  const sources = payload.sources.slice(0, 3).map((item) => item as Record<string, unknown>);
  const executive_points: BriefPoint[] = brief.executive_summary
    ? [
        {
          text: brief.executive_summary,
          type: "interpretation",
          evidence_strength: null,
          source_url: null,
        },
      ]
    : [];

  const lines = [
    `# **${company} (${ticker})**`,
    "## Latest reporting research brief",
    "",
    ...formatSection("Executive summary", executive_points, "No executive summary returned."),
    "",
    ...formatSection("What changed", brief.what_changed),
    "",
    ...formatSection("What matters most now", brief.what_matters_most_now),
    "",
    ...formatSection("Bull points", brief.bull_points),
    "",
    ...formatSection(
      "Bear points",
      brief.bear_points,
      "Model did not identify clear bear points from the selected evidence in this run.",
    ),
    "",
    ...formatSection("What to watch next", brief.what_to_watch_next),
    "",
    "### Evidence quality",
    `- **Strong:** ${quality.strong}`,
    `- **Medium:** ${quality.medium}`,
    `- **Weak:** ${quality.weak}`,
    "",
    "### Sources used",
    ...(sources.length > 0
      ? sources.map((source, index) => formatSource(source, index))
      : ["- No sources"]),
    "",
    "### Disclaimer",
    `- ${payload.disclaimer || "This is not investment advice."}`,
  ];

  if (payload.warning) {
    lines.push("", "### Warning", `- ${payload.warning}`);
  }
  if (payload.error) {
    lines.push("", "### Error", `- ${payload.error}`);
  }

  return lines.join("\n");
}

export function getVisibleSuggestions(input: string): string[] {
  const query = input.trim().toLowerCase();
  if (!query) {
    return SUGGESTED_PROMPTS.slice(0, 5);
  }
  return SUGGESTED_PROMPTS.filter((prompt) => prompt.toLowerCase().includes(query)).slice(0, 5);
}

export function getAnalyzeErrorMessage(error: unknown, timeoutMs: number): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return `Request timed out after ${Math.round(timeoutMs / 1000)}s`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}
