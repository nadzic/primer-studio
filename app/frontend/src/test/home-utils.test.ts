import { describe, expect, it } from "vitest";

import {
  formatResearchReply,
  getAnalyzeErrorMessage,
  getVisibleSuggestions,
} from "../components/home/utils";
import { ResearchResponse } from "../components/home/types";

describe("home utils", () => {
  it("formats research response into plain text brief", () => {
    const reply = formatResearchReply({
      company: "NVIDIA Corporation",
      ticker: "NVDA",
      brief: {
        executive_summary: "Revenue grew and guidance improved.",
        what_changed: [
          {
            text: "Revenue up YoY",
            type: "fact",
            evidence_strength: "strong",
            source_url: "https://example.com/earnings",
          },
        ],
        what_matters_most_now: [
          {
            text: "Data center demand remains strong",
            type: "interpretation",
            evidence_strength: "medium",
            source_url: null,
          },
        ],
        bull_points: [
          { text: "Strong AI demand", type: "fact", evidence_strength: "strong", source_url: null },
        ],
        bear_points: [
          {
            text: "Gross margin pressure risk",
            type: "interpretation",
            evidence_strength: "medium",
            source_url: null,
          },
        ],
        what_to_watch_next: [
          {
            text: "Next-quarter guidance",
            type: "fact",
            evidence_strength: "medium",
            source_url: null,
          },
        ],
      },
      evidence_quality_summary: { strong: 4, medium: 3, weak: 1 },
      sources: [
        {
          title: "Official earnings release",
          source_type: "earnings_release",
          final_source_score: 0.95,
          url: "https://example.com/source",
        },
      ],
      selected_evidence: [],
      discarded_evidence_count: 3,
      disclaimer: "This is not investment advice.",
      warning: null,
      error: null,
    } satisfies ResearchResponse);

    expect(reply).toContain("# **NVIDIA Corporation (NVDA)**");
    expect(reply).toContain("## Latest reporting research brief");
    expect(reply).toContain("### Executive summary");
    expect(reply).toContain("- **[FACT | strong]** Revenue up YoY ([source](https://example.com/earnings))");
    expect(reply).toContain("### Evidence quality");
    expect(reply).toContain("- **Strong:** 4");
    expect(reply).toContain("### Disclaimer");
    expect(reply).toContain("- [1. Official earnings release](https://example.com/source)");
  });

  it("returns suggestions filtered by input and limited to max five", () => {
    const suggestions = getVisibleSuggestions("research nvda");
    expect(suggestions.length).toBeLessThanOrEqual(5);
    expect(suggestions[0]).toContain("NVDA");
  });

  it("formats timeout and generic errors", () => {
    const timeoutMessage = getAnalyzeErrorMessage(
      new DOMException("The operation was aborted", "AbortError"),
      45_000,
    );
    expect(timeoutMessage).toBe("Request timed out after 45s");

    expect(getAnalyzeErrorMessage(new Error("boom"), 30_000)).toBe("boom");
    expect(getAnalyzeErrorMessage("bad", 30_000)).toBe("Unknown error");
  });

  it("uses explicit fallback when no bear points are returned", () => {
    const reply = formatResearchReply({
      company: "NVIDIA Corporation",
      ticker: "NVDA",
      brief: {
        executive_summary: null,
        what_changed: [],
        what_matters_most_now: [],
        bull_points: [],
        bear_points: [],
        what_to_watch_next: [],
      },
      evidence_quality_summary: { strong: 0, medium: 0, weak: 0 },
      sources: [],
      selected_evidence: [],
      discarded_evidence_count: 0,
      disclaimer: "This is not investment advice.",
      warning: null,
      error: null,
    } satisfies ResearchResponse);

    expect(reply).toContain("### Bear points");
    expect(reply).toContain(
      "Model did not identify clear bear points from the selected evidence in this run.",
    );
  });
});
