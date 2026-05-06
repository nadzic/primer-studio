from __future__ import annotations

from typing import Any, TypedDict


class NodesResearchState(TypedDict, total=False):
    # Input
    query: str
    input_query: str

    # Entity normalization
    company_name: str | None
    symbol: str | None
    sector: str | None
    industry: str | None

    # Retrieval planning + results
    search_queries: list[str]
    search_plan: list[dict[str, str]]
    sources: list[dict[str, Any]]
    ranked_sources: list[dict[str, Any]]

    # Evidence pipeline
    evidences: list[dict[str, Any]]
    classified_evidences: list[dict[str, Any]]
    selected_evidences: list[dict[str, Any]]
    discarded_evidence: list[dict[str, Any]]

    # Output
    research_summary: str | None
    research_brief: dict[str, Any]
    research_citations: list[str]

    # Diagnostics
    warning: str | None
    error: str | None
