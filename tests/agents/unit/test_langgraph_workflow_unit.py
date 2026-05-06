from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pytest
from langgraph.graph import END, START, StateGraph

from app.agents.graph import workflow
from app.agents.graph.state_models.nodes_research_state import NodesResearchState

try:
    from langgraph.checkpoint.memory import InMemorySaver as MemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver  # type: ignore[attr-defined]


NODE_SEQUENCE: list[tuple[str, str]] = [
    ("resolve_company", "company_resolver_node"),
    ("plan_search", "search_planner_node"),
    ("search_public_sources", "public_source_searcher_node"),
    ("rank_sources", "source_ranker_node"),
    ("extract_evidence", "evidence_extractor_node"),
    ("classify_evidence", "evidence_classifier_node"),
    ("select_evidence", "evidence_selector_node"),
    ("synthesize_brief", "research_synthesizer_node"),
]


def _node_path(state: Mapping[str, object]) -> list[str]:
    warning = str(state.get("warning") or "").strip()
    if not warning:
        return []
    return [part.strip() for part in warning.split("->") if part.strip()]


def _as_warning(path: list[str]) -> str | None:
    return " -> ".join(path) if path else None


def _stub_node(node_name: str):
    def _node(state: Mapping[str, object]) -> dict[str, object | None]:
        path = _node_path(state)
        path.append(node_name)
        return {"warning": _as_warning(path), "error": None}

    return _node


def _patch_workflow_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    for node_name, attribute_name in NODE_SEQUENCE:
        monkeypatch.setattr(workflow, attribute_name, _stub_node(node_name))


def _build_graph_with_checkpointer():
    graph = StateGraph(NodesResearchState)
    for node_name, attribute_name in NODE_SEQUENCE:
        node_fn = getattr(workflow, attribute_name)
        graph.add_node(node_name, action=cast(Any, workflow._adapt_node(node_fn)))

    graph.add_edge(START, NODE_SEQUENCE[0][0])
    for (current, _), (nxt, _) in zip(NODE_SEQUENCE, NODE_SEQUENCE[1:], strict=False):
        graph.add_edge(current, nxt)
    graph.add_edge(NODE_SEQUENCE[-1][0], END)
    return graph.compile(checkpointer=MemorySaver())


@pytest.mark.unit
def test_langgraph_workflow_basic_execution_runs_all_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_nodes(monkeypatch)
    compiled_graph = workflow.build_graph()

    result = compiled_graph.invoke({"query": "Research NVDA"})

    assert result["error"] is None
    assert result["warning"] == _as_warning([name for name, _ in NODE_SEQUENCE])


@pytest.mark.unit
def test_langgraph_workflow_individual_node_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_nodes(monkeypatch)
    compiled_graph = workflow.build_graph()

    node_result = compiled_graph.nodes["plan_search"].invoke(
        {"query": "Research NVDA", "warning": "resolve_company"},
    )

    assert node_result["error"] is None
    assert node_result["warning"] == "resolve_company -> plan_search"


@pytest.mark.unit
def test_langgraph_workflow_partial_execution_from_node_to_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_workflow_nodes(monkeypatch)
    compiled_graph = _build_graph_with_checkpointer()
    thread_id = "langgraph-test-thread"

    compiled_graph.update_state(
        config={"configurable": {"thread_id": thread_id}},
        values={"query": "Research NVDA", "warning": "resolve_company"},
        as_node="resolve_company",
    )

    result = compiled_graph.invoke(
        None,
        config={"configurable": {"thread_id": thread_id}},
        interrupt_after="rank_sources",
    )

    assert result["error"] is None
    assert (
        result["warning"]
        == "resolve_company -> plan_search -> search_public_sources -> rank_sources"
    )
