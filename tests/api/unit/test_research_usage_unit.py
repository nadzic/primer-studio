from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _StubGraph:
    def invoke(self, input: dict[str, object], /) -> dict[str, object]:
        return {
            "company_name": "Microsoft Corporation",
            "symbol": "MSFT",
            "ranked_sources": [],
            "selected_evidences": [],
            "classified_evidences": [],
            "research_summary": "Summary",
            "research_brief": {
                "executive_summary": "Summary",
                "what_changed": [],
                "what_matters_most_now": [],
                "bull_points": [],
                "bear_points": [],
                "what_to_watch_next": [],
                "disclaimer": "This is not investment advice.",
            },
            "warning": None,
            "error": None,
        }


@pytest.mark.unit
def test_research_route_returns_usage_snapshot_even_after_tracker_closes(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import research as research_route

    active = {"value": False}

    @contextmanager
    def _fake_usage_tracker() -> Iterator[None]:
        active["value"] = True
        try:
            yield
        finally:
            active["value"] = False

    def _fake_get_llm_usage() -> dict[str, int] | None:
        if not active["value"]:
            return None
        return {"prompt_tokens": 1200, "completion_tokens": 800, "total_tokens": 2000}

    @contextmanager
    def _fake_llm_request_overrides(*, provider: str | None = None, model_name: str | None = None):
        del provider, model_name
        yield

    monkeypatch.setattr(research_route, "_GRAPH", _StubGraph())
    monkeypatch.setattr(research_route, "llm_usage_tracker", _fake_usage_tracker)
    monkeypatch.setattr(research_route, "get_llm_usage", _fake_get_llm_usage)
    monkeypatch.setattr(research_route, "llm_request_overrides", _fake_llm_request_overrides)

    client = TestClient(app)
    response = client.post("/api/v1/research", json={"query": "Research MSFT"})

    assert response.status_code == 200
    usage = response.json().get("usage")
    assert usage == {"prompt_tokens": 1200, "completion_tokens": 800, "total_tokens": 2000}
