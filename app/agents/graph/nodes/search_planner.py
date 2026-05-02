from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.observability.tracing import observe


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return out


def _dedupe_plan_keep_order(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in items:
        query = str(item.get("query") or "").strip()
        purpose = str(item.get("purpose") or "").strip()
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"query": query, "purpose": purpose or "general_public_context"})
    return out


def _entity_label(company_name: str, symbol: str, query: str) -> str:
    if company_name and symbol:
        return f"{company_name} ({symbol})"
    if company_name:
        return company_name
    if symbol:
        return symbol
    return query


def _build_search_plan(entity: str, symbol: str) -> list[dict[str, str]]:
    subject = entity.strip()
    ticker_or_subject = symbol or subject
    if not subject:
        return []

    plan = [
        {
            "query": (
                f"{subject} latest quarterly earnings results "
                "investor relations press release"
            ),
            "purpose": "official_earnings_release",
        },
        {
            "query": f"{ticker_or_subject} latest 10-Q SEC filing revenue margin guidance",
            "purpose": "official_regulatory_filing",
        },
        {
            "query": f"{subject} latest earnings call transcript prepared remarks Q&A",
            "purpose": "management_commentary",
        },
        {
            "query": f"{subject} latest earnings results Reuters analysis",
            "purpose": "reputable_secondary_context",
        },
        {
            "query": f"{subject} analyst reaction after earnings",
            "purpose": "optional_market_sentiment",
        },
    ]
    return _dedupe_plan_keep_order(plan)


@observe(name="agents.graph.nodes.search_planner.search_planner_node")
def search_planner_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Create a purpose-driven search plan and a plain query list to feed retrieval.
    """
    try:
        query = str(state.get("query") or state.get("input_query") or "").strip()
        company_name = str(state.get("company_name") or "").strip()
        symbol = str(state.get("symbol") or "").strip().upper()

        entity = _entity_label(company_name=company_name, symbol=symbol, query=query)
        search_plan = _build_search_plan(entity=entity, symbol=symbol)

        search_queries = [item["query"] for item in search_plan]
        if query:
            search_queries.insert(0, query)
        if company_name:
            search_queries.insert(1 if query else 0, company_name)

        planned = _dedupe_keep_order(search_queries)[:8]
        capped_plan: list[dict[str, Any]] = []
        for item in search_plan:
            q = item.get("query")
            p = item.get("purpose")
            if q in planned and p is not None:
                capped_plan.append({"query": q, "purpose": p})

        return {
            "search_queries": planned,
            "search_plan": capped_plan,
            "warning": state.get("warning"),
            "error": None,
        }
    except Exception as exc:
        return {
            "search_queries": state.get("search_queries"),
            "search_plan": state.get("search_plan"),
            "warning": f"search_planner fallback: {exc}",
            "error": None,
        }
