from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_VALUE_RE = re.compile(
    r"(-?\d+(?:\.\d+)?%|\$?\d+(?:\.\d+)?\s?(?:billion|million|bn|m|b)|\$\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)
_PERIOD_RE = re.compile(r"\b(q[1-4]\s*20\d{2}|fy\s*20\d{2}|20\d{2})\b", flags=re.IGNORECASE)

_METRIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("revenue_growth", ("revenue", "sales", "top line")),
    ("eps_profit_change", ("eps", "earnings per share", "profit", "net income")),
    ("margin", ("gross margin", "operating margin", "margin", "ebitda margin")),
    ("segment_performance", ("segment", "datacenter", "gaming", "cloud", "enterprise", "consumer")),
    ("guidance", ("guidance", "outlook", "forecast", "expects", "expected")),
    (
        "management_commentary",
        ("management said", "management noted", "ceo said", "cfo said", "prepared remarks"),
    ),
    ("demand_signal", ("demand", "orders", "backlog", "bookings", "pipeline")),
    ("cost_capex_signal", ("capex", "opex", "operating expense", "cost", "spend", "spending")),
    ("risk_disclosure", ("risk", "headwind", "lawsuit", "regulatory", "uncertainty", "pressure")),
    ("market_reaction", ("shares", "stock", "rose", "fell", "market reaction", "after-hours")),
)


def _normalize_sentence(sentence: str) -> str:
    return " ".join(sentence.split()).strip()


def _detect_metric(text: str) -> str | None:
    lower = text.lower()
    for metric, markers in _METRIC_KEYWORDS:
        if any(marker in lower for marker in markers):
            return metric
    return None


def _detect_category(metric: str | None) -> str:
    if metric in {"revenue_growth", "eps_profit_change"}:
        return "financial_result"
    if metric == "margin":
        return "margin"
    if metric == "guidance":
        return "guidance"
    if metric == "segment_performance":
        return "segment_performance"
    if metric == "management_commentary":
        return "management_commentary"
    if metric == "demand_signal":
        return "demand_signal"
    if metric == "cost_capex_signal":
        return "cost_capex_signal"
    if metric == "risk_disclosure":
        return "risk_disclosure"
    if metric == "market_reaction":
        return "market_reaction"
    return "general"


def _detect_comparison_type(text: str) -> str | None:
    lower = text.lower()
    if any(
        marker in lower for marker in ("yoy", "year over year", "vs last year", "from last year")
    ):
        return "YoY"
    if any(
        marker in lower
        for marker in ("qoq", "quarter over quarter", "sequential", "vs previous quarter")
    ):
        return "QoQ"
    if any(
        marker in lower for marker in ("guidance", "outlook", "forecast", "expects", "expected")
    ):
        return "guidance_change"
    if any(
        marker in lower
        for marker in ("management said", "management noted", "commented", "highlighted")
    ):
        return "narrative_change"
    return None


def _extract_period(text: str) -> str | None:
    m = _PERIOD_RE.search(text)
    if m:
        return m.group(1).upper().replace("  ", " ")
    lower = text.lower()
    if any(marker in lower for marker in ("latest quarter", "this quarter", "quarterly results")):
        return "latest_quarter"
    return None


def _extract_value(text: str) -> str | None:
    m = _VALUE_RE.search(text)
    return m.group(1) if m else None


def _build_evidence_item(
    sentence: str,
    chunk: dict[str, Any],
    source_rank: int | None,
    idx: int,
) -> dict[str, Any] | None:
    claim = _normalize_sentence(sentence)
    if not claim:
        return None

    metric = _detect_metric(claim)
    # Keep only evidence relevant to the required extraction dimensions.
    if metric is None:
        return None

    source_url = str(chunk.get("url") or chunk.get("source_id") or "").strip()
    source_type = str(chunk.get("source_type") or "unknown").strip()
    category = _detect_category(metric)
    comparison_type = _detect_comparison_type(claim)
    period = _extract_period(claim)
    value = _extract_value(claim)

    evidence_id = f"{source_url or 'source'}:{source_rank or 0}:{idx}"
    return {
        # Schema-aligned fields
        "claim": claim,
        "category": category,
        "source_url": source_url,
        "source_type": source_type,
        "period": period,
        "metric": metric,
        "value": value,
        "comparison_type": comparison_type,
        "raw_quote_or_snippet": claim[:500],
        # Backward-compatible fields used by downstream nodes
        "text": claim,
        "source": source_url or None,
        "source_rank": source_rank,
        "chunk_text": str(chunk.get("text") or "")[:600],
        "evidence_id": evidence_id,
    }


def _extract_evidence_from_chunk(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(chunk.get("text") or "").strip()
    if not text:
        return []

    rank = chunk.get("rank")
    try:
        rank_i = int(rank) if rank is not None else None
    except Exception:
        rank_i = None

    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    parts = parts[:8]

    evidences: list[dict[str, Any]] = []
    for idx, sentence in enumerate(parts, start=1):
        ev = _build_evidence_item(sentence=sentence, chunk=chunk, source_rank=rank_i, idx=idx)
        if ev is not None:
            evidences.append(ev)
    return evidences


def _llm_extract_evidences(ranked_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload_sources: list[dict[str, Any]] = []
    for idx, source in enumerate(ranked_sources[:18]):
        payload_sources.append(
            {
                "idx": idx,
                "source_url": str(source.get("url") or source.get("source_id") or "").strip(),
                "source_type": str(source.get("source_type") or "").strip(),
                "source_rank": source.get("rank"),
                "text": str(source.get("text") or "").strip()[:1500],
            }
        )

    result = invoke_prompt_json(
        prompt_filename="evidence_extractor.md",
        payload={"sources": payload_sources},
        output_schema_hint="""
{
  "evidences": [
    {
      "source_idx": 0,
      "claim": "string",
      "category": "financial_result|margin|guidance|segment_performance|management_commentary|
                   demand_signal|cost_capex_signal|risk_disclosure|market_reaction|general",
      "period": "string|null",
      "metric": "string|null",
      "value": "string|null",
      "comparison_type": "YoY|QoQ|guidance_change|narrative_change|null",
      "raw_quote_or_snippet": "string|null"
    }
  ]
}
""".strip(),
    )

    raw_evidences = result.get("evidences") if isinstance(result, dict) else None
    if not isinstance(raw_evidences, list):
        return []

    out: list[dict[str, Any]] = []
    for idx, ev in enumerate(raw_evidences, start=1):
        if not isinstance(ev, dict):
            continue
        source_idx = ev.get("source_idx")
        if not isinstance(source_idx, int | float | str):
            continue
        try:
            source_i = int(source_idx)
        except Exception:
            continue
        if source_i < 0 or source_i >= len(payload_sources):
            continue
        source = payload_sources[source_i]
        claim = _normalize_sentence(str(ev.get("claim") or "").strip())
        if not claim:
            continue
        source_url = source["source_url"]
        source_rank = source.get("source_rank")
        evidence_id = f"{source_url or 'source'}:{source_rank or 0}:{idx}"
        metric = str(ev.get("metric") or "").strip() or _detect_metric(claim)
        category = str(ev.get("category") or "").strip() or _detect_category(metric)
        period = str(ev.get("period") or "").strip() or _extract_period(claim)
        value = str(ev.get("value") or "").strip() or _extract_value(claim)
        comparison_type = str(ev.get("comparison_type") or "").strip() or _detect_comparison_type(
            claim
        )
        out.append(
            {
                "claim": claim,
                "category": category,
                "source_url": source_url,
                "source_type": source["source_type"] or "unknown",
                "period": period or None,
                "metric": metric or None,
                "value": value or None,
                "comparison_type": comparison_type or None,
                "raw_quote_or_snippet": str(ev.get("raw_quote_or_snippet") or claim)[:500],
                "text": claim,
                "source": source_url or None,
                "source_rank": source_rank,
                "chunk_text": source["text"][:600],
                "evidence_id": evidence_id,
            }
        )
    return out


@observe(name="agents.graph.nodes.evidence_extractor.evidence_extractor_node")
def evidence_extractor_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Convert ranked source chunks into structured, atomic evidence items.

    Output:
    - evidences: list[dict] with schema-aligned fields:
      claim, category, source_url, source_type, period, metric, value, comparison_type
    """
    try:
        ranked_sources = state.get("ranked_sources")
        if not isinstance(ranked_sources, list) or not ranked_sources:
            return {"evidences": [], "warning": state.get("warning"), "error": None}

        llm_warning: str | None = None
        try:
            llm_evidences = _llm_extract_evidences(ranked_sources)
            if llm_evidences:
                return {
                    "evidences": llm_evidences[:80],
                    "warning": state.get("warning"),
                    "error": None,
                }
        except TimeoutError:
            # Expected degradation path: heuristic extractor below is sufficient.
            llm_warning = None
        except Exception as exc:
            llm_warning = f"evidence_extractor LLM fallback: {exc}"

        evidences: list[dict[str, Any]] = []
        seen_claims: set[str] = set()
        for src in ranked_sources[:18]:
            if not isinstance(src, dict):
                continue
            for ev in _extract_evidence_from_chunk(src):
                key = (
                    str(ev.get("claim") or "").strip().lower()
                    + "||"
                    + str(ev.get("source_url") or "").strip().lower()
                )
                if not key or key in seen_claims:
                    continue
                seen_claims.add(key)
                evidences.append(ev)

        warning_parts = [str(state.get("warning") or "").strip()]
        if llm_warning:
            warning_parts.append(llm_warning)
        return {
            "evidences": evidences[:80],
            "warning": " | ".join(part for part in warning_parts if part) or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "evidences": state.get("evidences"),
            "warning": f"evidence_extractor fallback: {exc}",
            "error": None,
        }
