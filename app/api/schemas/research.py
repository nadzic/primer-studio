from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User research query (e.g. NVDA)")
    model: str | None = Field(
        default=None,
        description="Optional LLM model override for this request (e.g. gpt-4o-mini, gpt-5.5, claude-4.6-sonnet).",
    )
    provider: Literal["openai", "anthropic"] | None = Field(
        default=None, description="Optional LLM provider override for this request."
    )


class BriefPoint(BaseModel):
    text: str = Field(..., min_length=1)
    type: Literal["fact", "interpretation"] = "interpretation"
    evidence_strength: Literal["strong", "medium", "weak"] | None = None
    evidence_id: str | None = None
    source_url: str | None = None


class Brief(BaseModel):
    executive_summary: str | None = None
    workflow_trace: list[str] = Field(default_factory=list)
    evidence_strength_rubric: list[str] = Field(default_factory=list)
    what_changed: list[BriefPoint] = Field(default_factory=list)
    what_matters_most_now: list[BriefPoint] = Field(default_factory=list)
    bull_points: list[BriefPoint] = Field(default_factory=list)
    bear_points: list[BriefPoint] = Field(default_factory=list)
    what_to_watch_next: list[BriefPoint] = Field(default_factory=list)


class EvidenceQualitySummary(BaseModel):
    strong: int = 0
    medium: int = 0
    weak: int = 0


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ResearchResponse(BaseModel):
    company: str | None = None
    ticker: str | None = None
    brief: Brief
    evidence_quality_summary: EvidenceQualitySummary

    sources: list[dict[str, Any]] = Field(default_factory=list)
    selected_evidence: list[dict[str, Any]] = Field(default_factory=list)
    discarded_evidence_count: int = 0
    disclaimer: str = "This is not investment advice."

    usage: TokenUsage | None = None
    warning: str | None = None
    error: str | None = None


class ResearchFollowupRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User follow-up question about the report.")
    company: str | None = None
    ticker: str | None = None
    brief: Brief = Field(..., description="Structured brief from the research run.")
    selected_evidence: list[dict[str, Any]] = Field(
        default_factory=list, description="Selected evidence payload for grounding."
    )
    chat_history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Optional prior chat turns, each: {role: user|assistant, content: string}.",
    )
    model: str | None = Field(default=None, description="Optional LLM model override for this follow-up.")
    provider: Literal["openai", "anthropic"] | None = Field(
        default=None, description="Optional LLM provider override for this follow-up."
    )


class ResearchFollowupResponse(BaseModel):
    answer: str
    disclaimer: str = "This is not investment advice."
