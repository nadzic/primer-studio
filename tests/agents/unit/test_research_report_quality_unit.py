from __future__ import annotations

import pytest

from app.agents.graph.nodes import public_source_searcher as public_source_searcher_mod
from app.agents.graph.nodes.company_resolver import company_resolver_node
from app.agents.graph.nodes.research_synthesizer import research_synthesizer_node
from app.agents.graph.nodes.search_planner import search_planner_node
from app.agents.services.web_search_service import WebSearchResult


def _raise_timeout(**kwargs):
    raise TimeoutError("LLM step timed out")


@pytest.mark.unit
def test_company_resolver_adds_sector_and_industry_for_mag7() -> None:
    out = company_resolver_node({"query": "Research MSFT"})
    assert out.get("symbol") == "MSFT"
    assert out.get("sector") == "Information Technology"
    assert "Software" in str(out.get("industry") or "")


@pytest.mark.unit
def test_synthesizer_keeps_changed_and_matters_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.graph.nodes.research_synthesizer.invoke_prompt_json",
        _raise_timeout,
    )
    selected = [
        {
            "evidence_id": "e1",
            "claim": "Revenue increased 18% year-over-year in Q2.",
            "source_url": "https://example.com/a",
            "source_type": "earnings_release",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["what_changed", "bull_points"],
            "inclusion_score": 0.95,
            "confidence": 0.95,
        },
        {
            "evidence_id": "e2",
            "claim": "Gross margin declined 120 bps due to mix headwinds.",
            "source_url": "https://example.com/b",
            "source_type": "sec_filing",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["what_matters_now", "bear_points"],
            "inclusion_score": 0.9,
            "confidence": 0.9,
        },
        {
            "evidence_id": "e3",
            "claim": "Management guided next-quarter gross margin to 74%.",
            "source_url": "https://example.com/c",
            "source_type": "earnings_call_transcript",
            "evidence_strength": "medium",
            "fact_or_interpretation": "fact",
            "used_for": ["what_to_watch_next", "what_matters_now"],
            "inclusion_score": 0.88,
            "confidence": 0.88,
        },
        {
            "evidence_id": "e4",
            "claim": "Operating cash flow rose to $10 billion.",
            "source_url": "https://example.com/d",
            "source_type": "sec_filing",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["bull_points", "what_matters_now"],
            "inclusion_score": 0.86,
            "confidence": 0.86,
        },
        {
            "evidence_id": "e5",
            "claim": "Export restrictions remain a risk to China sales.",
            "source_url": "https://example.com/e",
            "source_type": "sec_filing",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["bear_points", "what_to_watch_next"],
            "inclusion_score": 0.84,
            "confidence": 0.84,
        },
        {
            "evidence_id": "e6",
            "claim": "Data center backlog remains elevated.",
            "source_url": "https://example.com/f",
            "source_type": "earnings_release",
            "evidence_strength": "medium",
            "fact_or_interpretation": "fact",
            "used_for": ["what_matters_now"],
            "inclusion_score": 0.82,
            "confidence": 0.82,
        },
    ]

    out = research_synthesizer_node(
        {
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
            "selected_evidences": selected,
            "ranked_sources": [],
            "warning": None,
        }
    )
    brief = out.get("research_brief")
    assert isinstance(brief, dict)

    def _ids(section: str) -> set[str]:
        items = brief.get(section)
        if not isinstance(items, list):
            return set()
        return {str(item.get("evidence_id") or "") for item in items if isinstance(item, dict)}

    changed_ids = _ids("what_changed")
    matters_ids = _ids("what_matters_most_now")
    bull_ids = _ids("bull_points")
    bear_ids = _ids("bear_points")

    assert changed_ids
    assert matters_ids
    assert changed_ids.isdisjoint(matters_ids)
    assert bull_ids.isdisjoint(bear_ids)


@pytest.mark.unit
def test_synthesizer_uses_sector_context_for_what_matters_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.graph.nodes.research_synthesizer.invoke_prompt_json",
        _raise_timeout,
    )
    selected = [
        {
            "evidence_id": "chg",
            "claim": "Revenue increased 18% year-over-year in Q2.",
            "source_url": "https://example.com/a",
            "source_type": "earnings_release",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["what_changed"],
            "inclusion_score": 0.95,
            "confidence": 0.95,
        },
        {
            "evidence_id": "ctx",
            "claim": "Azure cloud pricing stayed stable while AI demand accelerated.",
            "source_url": "https://example.com/b",
            "source_type": "earnings_call_transcript",
            "evidence_strength": "medium",
            "fact_or_interpretation": "fact",
            "used_for": [],
            "inclusion_score": 0.9,
            "confidence": 0.9,
        },
    ]

    out = research_synthesizer_node(
        {
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
            "sector": "Information Technology",
            "industry": "Software and Cloud Platforms",
            "selected_evidences": selected,
            "ranked_sources": [],
            "warning": None,
        }
    )
    brief = out.get("research_brief")
    assert isinstance(brief, dict)
    matters = brief.get("what_matters_most_now")
    assert isinstance(matters, list)
    matters_ids = {str(item.get("evidence_id") or "") for item in matters if isinstance(item, dict)}
    assert "ctx" in matters_ids


@pytest.mark.unit
def test_synthesizer_reuses_sparse_evidence_for_bull_and_bear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.graph.nodes.research_synthesizer.invoke_prompt_json",
        _raise_timeout,
    )
    selected = [
        {
            "evidence_id": "e1",
            "claim": "Operating cash flow rose 12% year-over-year in the latest quarter.",
            "source_url": "https://example.com/cash-flow",
            "source_type": "sec_filing",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["what_changed"],
            "inclusion_score": 0.95,
            "confidence": 0.95,
        },
        {
            "evidence_id": "e2",
            "claim": "Margin headwinds are unlikely to abate in the near term.",
            "source_url": "https://example.com/headwinds",
            "source_type": "reputable_financial_news",
            "evidence_strength": "medium",
            "fact_or_interpretation": "interpretation",
            "used_for": ["what_matters_now"],
            "inclusion_score": 0.9,
            "confidence": 0.9,
        },
    ]

    out = research_synthesizer_node(
        {
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
            "selected_evidences": selected,
            "ranked_sources": [],
            "warning": None,
        }
    )
    brief = out.get("research_brief")
    assert isinstance(brief, dict)

    bull_points = brief.get("bull_points")
    bear_points = brief.get("bear_points")
    assert isinstance(bull_points, list)
    assert isinstance(bear_points, list)
    assert {point.get("evidence_id") for point in bull_points if isinstance(point, dict)} == {"e1"}
    assert {point.get("evidence_id") for point in bear_points if isinstance(point, dict)} == {"e2"}


@pytest.mark.unit
def test_synthesizer_adds_stock_specific_scenario_bear_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.agents.graph.nodes.research_synthesizer.invoke_prompt_json",
        _raise_timeout,
    )
    selected = [
        {
            "evidence_id": "e1",
            "claim": "Data center revenue rose 18% year-over-year in the latest quarter.",
            "source_url": "https://example.com/nvda",
            "source_type": "earnings_release",
            "evidence_strength": "strong",
            "fact_or_interpretation": "fact",
            "used_for": ["what_changed", "bull_points"],
            "inclusion_score": 0.95,
            "confidence": 0.95,
        },
    ]

    out = research_synthesizer_node(
        {
            "company_name": "NVIDIA Corporation",
            "symbol": "NVDA",
            "sector": "Information Technology",
            "industry": "Semiconductors and Accelerated Computing",
            "selected_evidences": selected,
            "ranked_sources": [],
            "warning": None,
        }
    )
    brief = out.get("research_brief")
    assert isinstance(brief, dict)

    bear_points = brief.get("bear_points")
    assert isinstance(bear_points, list)
    assert bear_points
    assert any(
        isinstance(point, dict)
        and str(point.get("text") or "").startswith("Scenario risk:")
        and point.get("evidence_strength") == "weak"
        and point.get("source_url") is None
        for point in bear_points
    )


@pytest.mark.unit
def test_search_planner_adds_risk_and_outlook_queries() -> None:
    out = search_planner_node(
        {
            "query": "Research Microsoft",
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
        }
    )
    search_plan = out.get("search_plan")
    assert isinstance(search_plan, list)
    queries = [
        str(item.get("query") or "").lower()
        for item in search_plan
        if isinstance(item, dict)
    ]
    assert any("risk factors" in query for query in queries)
    assert any("outlook guidance" in query for query in queries)


@pytest.mark.unit
def test_search_planner_adds_sector_context_queries() -> None:
    out = search_planner_node(
        {
            "query": "Research Microsoft",
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
            "sector": "Information Technology",
            "industry": "Software and Cloud Platforms",
        }
    )
    search_plan = out.get("search_plan")
    assert isinstance(search_plan, list)
    sector_queries = [
        str(item.get("query") or "").lower()
        for item in search_plan
        if isinstance(item, dict) and str(item.get("purpose") or "") == "sector_context"
    ]
    assert len(sector_queries) >= 1
    assert any("software and cloud platforms" in query for query in sector_queries)


@pytest.mark.unit
def test_public_source_searcher_fans_out_more_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def _fake_search_public_web(
        query: str,
        *,
        max_results: int,
        search_depth: str,
        timeout_s: float,
    ) -> list[WebSearchResult]:
        calls.append((query, max_results))
        return [
            WebSearchResult(
                rank=1,
                url=f"https://example.com/{len(calls)}",
                title="Example",
                snippet="Revenue increased year-over-year.",
                score=0.9,
                provider="tavily",
            )
        ]

    monkeypatch.setattr(public_source_searcher_mod, "web_search_available", lambda: True)
    monkeypatch.setattr(public_source_searcher_mod, "search_public_web", _fake_search_public_web)
    planned = [
        {"query": f"query-{i}", "purpose": "planned_search"}
        for i in range(1, 7)
    ]
    out = public_source_searcher_mod.public_source_searcher_node({"search_plan": planned})
    sources = out.get("sources")
    assert isinstance(sources, list)
    assert len(calls) == 5
    assert all(max_results == 8 for _, max_results in calls)
