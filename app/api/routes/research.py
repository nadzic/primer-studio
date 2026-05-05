from __future__ import annotations

import asyncio
from typing import Any, Literal, Protocol, cast

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.agents.graph.state_models.nodes_research_state import NodesResearchState
from app.agents.graph.workflow import build_graph
from app.agents.services.llm_service import get_llm_usage, llm_request_overrides, llm_usage_tracker
from app.api.schemas.research import (
    Brief,
    BriefPoint,
    EvidenceQualitySummary,
    ResearchFollowupRequest,
    ResearchFollowupResponse,
    ResearchRequest,
    ResearchResponse,
    TokenUsage,
)
from app.agents.services.prompt_llm_service import invoke_prompt_json

router = APIRouter()
RESEARCH_TIMEOUT_SECONDS = 180


class _GraphRunner(Protocol):
    def invoke(self, input: NodesResearchState, /) -> NodesResearchState: ...


_GRAPH = cast(_GraphRunner, cast(object, build_graph()))
PointType = Literal["fact", "interpretation"]
EvidenceStrength = Literal["strong", "medium", "weak"]


def _quality_bucket(source_rank: Any) -> str:
    try:
        sr = int(source_rank)
    except Exception:
        return "weak"
    if sr <= 3:
        return "strong"
    if sr <= 10:
        return "medium"
    return "weak"


def _evidence_quality(selected: list[dict[str, Any]]) -> EvidenceQualitySummary:
    strong = 0
    medium = 0
    weak = 0
    for ev in selected:
        bucket = _quality_bucket(ev.get("source_rank"))
        if bucket == "strong":
            strong += 1
        elif bucket == "medium":
            medium += 1
        else:
            weak += 1
    return EvidenceQualitySummary(strong=strong, medium=medium, weak=weak)


def _normalize_point_type(value: Any) -> PointType:
    normalized = str(value or "").strip().lower()
    if normalized in {"fact", "interpretation"}:
        return cast(PointType, normalized)
    return "interpretation"


def _normalize_strength(value: Any) -> EvidenceStrength | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"strong", "medium", "weak"}:
        return cast(EvidenceStrength, normalized)
    return None


def _infer_provider(provider: str | None, model: str | None) -> str | None:
    if provider:
        normalized = provider.strip().lower()
        return normalized if normalized in {"openai", "anthropic"} else None
    model_name = (model or "").strip().lower()
    if model_name.startswith("claude"):
        return "anthropic"
    if model_name:
        return "openai"
    return None


def _as_brief_points(value: Any) -> list[BriefPoint]:
    if not isinstance(value, list):
        return []
    out: list[BriefPoint] = []
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("claim") or "").strip()
            point_type = _normalize_point_type(
                item.get("type") or item.get("fact_or_interpretation")
            )
            strength = _normalize_strength(item.get("evidence_strength"))
            evidence_id = str(item.get("evidence_id") or "").strip() or None
            source_url = str(item.get("source_url") or item.get("source") or "").strip() or None
        else:
            text = str(item).strip()
            point_type = "interpretation"
            strength = None
            evidence_id = None
            source_url = None
        if text:
            out.append(
                BriefPoint(
                    text=text,
                    type=point_type,
                    evidence_strength=strength,
                    evidence_id=evidence_id,
                    source_url=source_url,
                )
            )
    return out


@router.post("/research", response_model=ResearchResponse)
async def research(payload: ResearchRequest) -> ResearchResponse:
    state: NodesResearchState = {
        "query": payload.query,
        "input_query": payload.query,
        "warning": None,
        "error": None,
    }

    try:
        provider = _infer_provider(payload.provider, payload.model)
        with llm_request_overrides(provider=provider, model_name=payload.model), llm_usage_tracker():
            result = await asyncio.wait_for(
                run_in_threadpool(_GRAPH.invoke, state),
                timeout=RESEARCH_TIMEOUT_SECONDS,
            )
    except TimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail=f"Research execution timed out after {RESEARCH_TIMEOUT_SECONDS}s",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research execution failed: {e}") from e

    company_name = cast(str | None, result.get("company_name"))
    symbol = cast(str | None, result.get("symbol"))

    ranked_sources = result.get("ranked_sources")
    sources: list[dict[str, Any]] = ranked_sources if isinstance(ranked_sources, list) else []

    selected = result.get("selected_evidences")
    selected_evidence: list[dict[str, Any]] = selected if isinstance(selected, list) else []

    classified = result.get("classified_evidences")
    classified_evidence: list[dict[str, Any]] = classified if isinstance(classified, list) else []

    discarded_evidence_count = max(0, len(classified_evidence) - len(selected_evidence))

    summary = cast(str | None, result.get("research_summary"))
    research_brief = result.get("research_brief")
    brief_data = research_brief if isinstance(research_brief, dict) else {}

    brief = Brief(
        executive_summary=cast(str | None, brief_data.get("executive_summary")) or summary,
        workflow_trace=cast(list[str], brief_data.get("workflow_trace")) if isinstance(brief_data.get("workflow_trace"), list) else [],
        evidence_strength_rubric=cast(list[str], brief_data.get("evidence_strength_rubric")) if isinstance(brief_data.get("evidence_strength_rubric"), list) else [],
        what_changed=_as_brief_points(brief_data.get("what_changed")),
        what_matters_most_now=_as_brief_points(brief_data.get("what_matters_most_now")),
        bull_points=_as_brief_points(brief_data.get("bull_points")),
        bear_points=_as_brief_points(brief_data.get("bear_points")),
        what_to_watch_next=_as_brief_points(brief_data.get("what_to_watch_next")),
    )
    disclaimer = str(brief_data.get("disclaimer") or "This is not investment advice.").strip()

    response = ResearchResponse(
        company=company_name,
        ticker=symbol,
        brief=brief,
        evidence_quality_summary=_evidence_quality(selected_evidence),
        sources=sources,
        selected_evidence=selected_evidence,
        discarded_evidence_count=discarded_evidence_count,
        disclaimer=disclaimer or "This is not investment advice.",
        usage=TokenUsage(**get_llm_usage()) if isinstance(get_llm_usage(), dict) else None,
        warning=cast(str | None, result.get("warning")),
        error=cast(str | None, result.get("error")),
    )
    return response


@router.post("/research/followup", response_model=ResearchFollowupResponse)
async def research_followup(payload: ResearchFollowupRequest) -> ResearchFollowupResponse:
    """
    Answer a follow-up question grounded on a previously generated research brief.
    """
    try:
        company = (payload.company or "").strip() or None
        ticker = (payload.ticker or "").strip().upper() or None

        brief = payload.brief.model_dump()
        selected_evidence = payload.selected_evidence[:40]
        history = payload.chat_history[-12:]

        provider = _infer_provider(payload.provider, payload.model)
        with llm_request_overrides(provider=provider, model_name=payload.model):
            result = await asyncio.to_thread(
                invoke_prompt_json,
                prompt_filename="research_followup.md",
                payload={
                    "company": company,
                    "ticker": ticker,
                    "brief": brief,
                    "selected_evidence": selected_evidence,
                    "chat_history": history,
                    "question": payload.question,
                },
                output_schema_hint='{"answer":"string"}',
            )
        answer = (
            str(result.get("answer") or "").strip()
            if isinstance(result, dict)
            else ""
        )
        if not answer:
            answer = "I couldn't generate a grounded answer from the provided brief and evidence."
        return ResearchFollowupResponse(answer=answer)
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Follow-up failed: {e}") from e
