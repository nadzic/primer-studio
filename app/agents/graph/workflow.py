# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from langgraph.graph import END, START, StateGraph

from app.agents.graph.nodes import (
    company_resolver_node,
    evidence_classifier_node,
    evidence_extractor_node,
    evidence_selector_node,
    public_source_searcher_node,
    research_synthesizer_node,
    search_planner_node,
    source_ranker_node,
)
from app.agents.graph.state_models.nodes_research_state import NodesResearchState


def _adapt_node(
    fn: Callable[[Mapping[str, object]], dict[str, object | None]],
) -> Callable[[NodesResearchState], dict[str, Any]]:
    def _inner(state: NodesResearchState) -> dict[str, Any]:
        return cast(dict[str, Any], fn(cast(Mapping[str, object], state)))

    return _inner


def build_graph():
    graph = StateGraph(NodesResearchState)

    # LangGraph's typing expects a Runnable-like StateNode; we keep a simple callable and cast.
    _ = graph.add_node("resolve_company", cast(Any, _adapt_node(company_resolver_node)))
    _ = graph.add_node("plan_search", cast(Any, _adapt_node(search_planner_node)))
    _ = graph.add_node("search_public_sources", cast(Any, _adapt_node(public_source_searcher_node)))
    _ = graph.add_node("rank_sources", cast(Any, _adapt_node(source_ranker_node)))
    _ = graph.add_node("extract_evidence", cast(Any, _adapt_node(evidence_extractor_node)))
    _ = graph.add_node("classify_evidence", cast(Any, _adapt_node(evidence_classifier_node)))
    _ = graph.add_node("select_evidence", cast(Any, _adapt_node(evidence_selector_node)))
    _ = graph.add_node("synthesize_brief", cast(Any, _adapt_node(research_synthesizer_node)))

    _ = graph.add_edge(START, "resolve_company")
    _ = graph.add_edge("resolve_company", "plan_search")
    _ = graph.add_edge("plan_search", "search_public_sources")
    _ = graph.add_edge("search_public_sources", "rank_sources")
    _ = graph.add_edge("rank_sources", "extract_evidence")
    _ = graph.add_edge("extract_evidence", "classify_evidence")
    _ = graph.add_edge("classify_evidence", "select_evidence")
    _ = graph.add_edge("select_evidence", "synthesize_brief")
    _ = graph.add_edge("synthesize_brief", END)

    return graph.compile()
