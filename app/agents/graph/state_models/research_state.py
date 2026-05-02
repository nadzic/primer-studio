from typing import Any, TypedDict


class ResearchState(TypedDict):
    user_query: str

    company_name: str | None
    ticker: str | None
    exchange: str | None

    search_plan: list[dict[str, Any]]
    raw_sources: list[dict[str, Any]]
    ranked_sources: list[dict[str, Any]]

    evidence_items: list[dict[str, Any]]
    classified_evidence: list[dict[str, Any]]
    selected_evidence: list[dict[str, Any]]
    discarded_evidence: list[dict[str, Any]]

    final_brief: dict[str, Any]
    errors: list[str]
