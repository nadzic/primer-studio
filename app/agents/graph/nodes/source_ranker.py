from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_QUARTER_MARKERS: tuple[str, ...] = (
    "q1",
    "q2",
    "q3",
    "q4",
    "quarter",
    "quarterly",
    "fiscal",
)
_LATEST_RESULT_MARKERS: tuple[str, ...] = (
    "latest",
    "earnings",
    "results",
    "press release",
    "10-q",
    "10-k",
    "8-k",
    "guidance",
)
_RECENT_MARKERS: tuple[str, ...] = (
    "today",
    "yesterday",
    "this week",
    "recent",
    "latest",
    "reported",
)
_CALIBRATED_WEIGHTS: dict[str, float] = {
    "reliability": 0.50,
    "relevance": 0.27,
    "recency": 0.18,
    "search_signal": 0.05,
}
_NEWSWIRE_HOST_MARKERS: tuple[str, ...] = (
    "reuters.com",
    "apnews.com",
    "finance.yahoo.com",
    "marketwatch.com",
    "cnbc.com",
    "wsj.com",
    "ft.com",
)
_OFFICIAL_SOURCE_TYPES: set[str] = {
    "sec_filing",
    "earnings_release",
    "company_presentation",
    "company_ir_page",
}


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _chunk_key(chunk: dict[str, Any]) -> str:
    return (
        str(chunk.get("source_id") or chunk.get("url") or "").strip().lower()
        + "||"
        + str(chunk.get("text") or "").strip()[:200].lower()
    )


def _extract_host(url: str) -> str:
    host = urlparse(url).netloc.lower().strip()
    return host[4:] if host.startswith("www.") else host


def _normalize_fingerprint_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120]


def _newswire_fingerprint(chunk: dict[str, Any]) -> str | None:
    url = str(chunk.get("url") or chunk.get("source_id") or "").strip()
    host = _extract_host(url)
    if not host or not _contains_any(host, _NEWSWIRE_HOST_MARKERS):
        return None
    title = str(chunk.get("title") or "").strip()
    text = str(chunk.get("text") or "").strip()
    base_text = title or text[:180]
    normalized = _normalize_fingerprint_text(base_text)
    if not normalized:
        return None
    return f"{normalized}"


def _newswire_fingerprint_counts(sources: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in sources:
        fp = _newswire_fingerprint(chunk)
        if not fp:
            continue
        counts[fp] = counts.get(fp, 0) + 1
    return counts


def _search_signal_score(chunk: dict[str, Any]) -> float:
    score = _to_float(chunk.get("score"))
    if score is not None:
        return _clamp01(score)
    rank = _to_int(chunk.get("rank"))
    if rank is not None and rank > 0:
        return _clamp01(1.0 / float(rank))
    return 0.35


def _latest_year_in_chunk(chunk: dict[str, Any]) -> int | None:
    text = str(chunk.get("text") or "").strip().lower()
    title = str(chunk.get("title") or "").strip().lower()
    combined = f"{title} {text}"
    years = [int(y) for y in _YEAR_RE.findall(combined)]
    return max(years) if years else None


def _normalized_source_type(chunk: dict[str, Any]) -> str:
    raw_type = str(chunk.get("source_type") or "").strip().lower()
    title = str(chunk.get("title") or "").strip().lower()
    text = str(chunk.get("text") or "").strip().lower()
    purpose = str(chunk.get("query_purpose") or "").strip().lower()
    combined = f"{title} {text} {purpose}"

    if raw_type == "public:sec_edgar":
        return "sec_filing"
    if "official_regulatory_filing" in purpose or _contains_any(
        combined, ("10-q", "10-k", "8-k", "sec filing")
    ):
        return "sec_filing"

    if raw_type == "public:company_ir":
        if _contains_any(combined, ("presentation", "deck", "slides")):
            return "company_presentation"
        if _contains_any(combined, ("press release", "financial results", "earnings release")):
            return "earnings_release"
        return "company_ir_page"

    if raw_type == "public:earnings_transcript":
        return "earnings_call_transcript"

    if raw_type == "public:financial_news":
        return "reputable_financial_news"

    if "official_earnings_release" in purpose:
        return "earnings_release"
    if "management_commentary" in purpose:
        return "earnings_call_transcript"
    if "reputable_secondary_context" in purpose:
        return "reputable_financial_news"

    return "analyst_or_commentary"


def _reliability_score(source_type: str, text: str) -> float:
    if source_type == "sec_filing":
        return 1.00
    if source_type == "earnings_release":
        return 0.95
    if source_type == "earnings_call_transcript":
        return 0.88
    if source_type == "company_presentation":
        return 0.84
    if source_type == "company_ir_page":
        return 0.82
    if source_type == "reputable_financial_news":
        return 0.72

    # Tier 4 range: analyst/blog/social commentary = 0.35-0.55.
    if _contains_any(text, ("analyst note", "research note", "opinion")):
        return 0.55
    if _contains_any(text, ("blog", "substack", "reddit", "x.com", "twitter", "social")):
        return 0.38
    return 0.45


def _relevance_score(chunk: dict[str, Any], normalized_source_type: str) -> float:
    title = str(chunk.get("title") or "").strip().lower()
    text = str(chunk.get("text") or "").strip().lower()
    purpose = str(chunk.get("query_purpose") or "").strip().lower()
    combined = f"{title} {text} {purpose}"
    base_search_score = _to_float(chunk.get("score")) or 0.0

    if (
        purpose in {"official_earnings_release", "official_regulatory_filing"}
        or _contains_any(combined, _LATEST_RESULT_MARKERS)
        and _contains_any(combined, _QUARTER_MARKERS)
    ):
        if normalized_source_type == "sec_filing":
            return 0.98
        if normalized_source_type == "earnings_release":
            return 0.96
        return 0.92

    if purpose in {"management_commentary", "reputable_secondary_context"} or _contains_any(
        combined,
        ("earnings call", "transcript", "prepared remarks", "guidance", "after earnings"),
    ):
        return 0.82 if base_search_score >= 0.5 else 0.76

    if _contains_any(combined, ("company", "market", "demand", "industry", "segment", "business")):
        return 0.58 if base_search_score >= 0.5 else 0.46

    return 0.32


def _recency_score(chunk: dict[str, Any], relevance_score: float) -> float:
    title = str(chunk.get("title") or "").strip().lower()
    text = str(chunk.get("text") or "").strip().lower()
    combined = f"{title} {text}"
    current_year = datetime.now(UTC).year
    years = [int(y) for y in _YEAR_RE.findall(combined)]
    newest_year = max(years) if years else None

    if (
        newest_year in {current_year, current_year - 1}
        and _contains_any(combined, _QUARTER_MARKERS)
        and relevance_score >= 0.9
    ):
        return 0.95
    if newest_year in {current_year, current_year - 1} or _contains_any(combined, _RECENT_MARKERS):
        return 0.72
    if newest_year is not None and newest_year <= current_year - 2:
        return 0.45
    return 0.62


def _calibrated_final_score(
    chunk: dict[str, Any],
    reliability_score: float,
    relevance_score: float,
    recency_score: float,
) -> float:
    search_signal = _search_signal_score(chunk)
    score = (
        (_CALIBRATED_WEIGHTS["reliability"] * reliability_score)
        + (_CALIBRATED_WEIGHTS["relevance"] * relevance_score)
        + (_CALIBRATED_WEIGHTS["recency"] * recency_score)
        + (_CALIBRATED_WEIGHTS["search_signal"] * search_signal)
    )
    return _clamp01(score)


def _score_adjustments(
    chunk: dict[str, Any],
    source_type: str,
    relevance_score: float,
    recency_score: float,
    fingerprint_counts: Mapping[str, int],
) -> tuple[float, list[str]]:
    penalty = 0.0
    bonus = 0.0
    notes: list[str] = []

    newest_year = _latest_year_in_chunk(chunk)
    current_year = datetime.now(UTC).year
    if newest_year is not None:
        age_years = current_year - newest_year
        if age_years >= 3:
            stale_penalty = 0.18 if source_type in {"reputable_financial_news", "analyst_or_commentary"} else 0.10
            penalty += stale_penalty
            notes.append(f"stale_penalty={stale_penalty:.2f}")
        elif age_years == 2:
            stale_penalty = 0.10 if source_type in {"reputable_financial_news", "analyst_or_commentary"} else 0.06
            penalty += stale_penalty
            notes.append(f"stale_penalty={stale_penalty:.2f}")

    fp = _newswire_fingerprint(chunk)
    if fp and source_type == "reputable_financial_news":
        duplicate_count = fingerprint_counts.get(fp, 1)
        if duplicate_count > 1:
            duplicate_penalty = min(0.16, 0.08 * float(duplicate_count - 1))
            penalty += duplicate_penalty
            notes.append(f"newswire_duplicate_penalty={duplicate_penalty:.2f}")

    if source_type in _OFFICIAL_SOURCE_TYPES and relevance_score >= 0.95 and recency_score >= 0.90:
        bonus = 0.03
        notes.append(f"official_fresh_bonus={bonus:.2f}")

    return (bonus - penalty), notes


def _build_reason(
    source_type: str,
    reliability_score: float,
    relevance_score: float,
    recency_score: float,
    final_source_score: float,
    search_signal_score: float,
    adjustments: list[str] | None = None,
) -> str:
    source_label = source_type.replace("_", " ")
    reason = (
        f"{source_label} source; reliability={reliability_score:.2f}, "
        f"relevance={relevance_score:.2f}, recency={recency_score:.2f}, "
        f"search_signal={search_signal_score:.2f}, final={final_source_score:.2f}."
    )
    if adjustments:
        reason += f" adjustments={', '.join(adjustments)}."
    return reason


def _llm_rank_sources(
    sources: list[dict[str, Any]],
    fingerprint_counts: Mapping[str, int],
) -> list[dict[str, Any]]:
    payload_sources: list[dict[str, Any]] = []
    for idx, source in enumerate(sources):
        payload_sources.append(
            {
                "idx": idx,
                "title": str(source.get("title") or "").strip(),
                "url": str(source.get("url") or source.get("source_id") or "").strip(),
                "text": str(source.get("text") or "").strip()[:900],
                "source_type": str(source.get("source_type") or "").strip(),
                "query_purpose": str(source.get("query_purpose") or "").strip(),
                "search_score": _to_float(source.get("score")),
            }
        )

    result = invoke_prompt_json(
        prompt_filename="source_ranker.md",
        payload={"sources": payload_sources},
        output_schema_hint="""
{
  "ranked_sources": [
    {
      "idx": 0,
      "source_type": "sec_filing|earnings_release|earnings_call_transcript|
                      company_presentation|company_ir_page|reputable_financial_news|
                      analyst_or_commentary",
      "reliability_score": 0.0,
      "relevance_score": 0.0,
      "recency_score": 0.0,
      "final_source_score": 0.0,
      "reason": "string"
    }
  ]
}
""".strip(),
    )

    ranked_sources = result.get("ranked_sources") if isinstance(result, dict) else None
    if not isinstance(ranked_sources, list):
        return []

    out: list[dict[str, Any]] = []
    used_indices: set[int] = set()
    for item in ranked_sources:
        if not isinstance(item, dict):
            continue
        idx = _to_int(item.get("idx"))
        if idx is None or idx < 0 or idx >= len(sources) or idx in used_indices:
            continue
        used_indices.add(idx)
        base = dict(sources[idx])
        source_type = str(item.get("source_type") or "").strip() or _normalized_source_type(base)
        reliability_score = _clamp01(_to_float(item.get("reliability_score")) or _reliability_score(source_type, str(base.get("text") or "").lower()))
        relevance_score = _clamp01(_to_float(item.get("relevance_score")) or _relevance_score(base, source_type))
        recency_score = _clamp01(_to_float(item.get("recency_score")) or _recency_score(base, relevance_score))
        llm_final_source_score = _to_float(item.get("final_source_score"))
        base["source_type"] = source_type
        base["reliability_score"] = round(reliability_score, 4)
        base["relevance_score"] = round(relevance_score, 4)
        base["recency_score"] = round(recency_score, 4)
        calibrated_score = _calibrated_final_score(
            base,
            reliability_score=reliability_score,
            relevance_score=relevance_score,
            recency_score=recency_score,
        )
        if llm_final_source_score is not None:
            blended = (0.7 * calibrated_score) + (0.3 * _clamp01(llm_final_source_score))
        else:
            blended = calibrated_score
        adjustment_delta, adjustment_notes = _score_adjustments(
            chunk=base,
            source_type=source_type,
            relevance_score=relevance_score,
            recency_score=recency_score,
            fingerprint_counts=fingerprint_counts,
        )
        final_source_score = _clamp01(blended + adjustment_delta)
        base["final_source_score"] = round(final_source_score, 4)
        base["ranking_adjustments"] = adjustment_notes
        base["reason"] = str(item.get("reason") or "").strip() or _build_reason(
            source_type=source_type,
            reliability_score=base["reliability_score"],
            relevance_score=base["relevance_score"],
            recency_score=base["recency_score"],
            final_source_score=final_source_score,
            search_signal_score=_search_signal_score(base),
            adjustments=adjustment_notes,
        )
        out.append(base)
    return out


@observe(name="agents.graph.nodes.source_ranker.source_ranker_node")
def source_ranker_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Rank and dedupe candidate sources/chunks from retrieval.

    Output:
    - ranked_sources: list[dict] (same shape as input chunks)
    """
    try:
        sources = state.get("sources")
        if not isinstance(sources, list) or not sources:
            return {"ranked_sources": [], "warning": state.get("warning"), "error": None}

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in sources:
            if not isinstance(raw, dict):
                continue
            key = _chunk_key(raw)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(raw)

        fingerprint_counts = _newswire_fingerprint_counts(deduped)

        llm_warning: str | None = None
        try:
            llm_ranked = _llm_rank_sources(deduped, fingerprint_counts=fingerprint_counts)
            if llm_ranked:
                ranked = sorted(
                    llm_ranked,
                    key=lambda chunk: (
                        _to_float(chunk.get("final_source_score")) or 0.0,
                        _to_float(chunk.get("reliability_score")) or 0.0,
                        _to_float(chunk.get("relevance_score")) or 0.0,
                        -(_to_int(chunk.get("rank")) or 999),
                    ),
                    reverse=True,
                )[:25]
                for idx, item in enumerate(ranked, start=1):
                    item["rank"] = idx
                return {
                    "ranked_sources": ranked,
                    "warning": state.get("warning"),
                    "error": None,
                }
        except Exception as exc:
            llm_warning = f"source_ranker LLM fallback: {exc}"

        enriched: list[dict[str, Any]] = []
        for chunk in deduped:
            normalized_source_type = _normalized_source_type(chunk)
            text = str(chunk.get("text") or "").strip().lower()
            reliability_score = _reliability_score(normalized_source_type, text)
            relevance_score = _relevance_score(chunk, normalized_source_type)
            recency_score = _recency_score(chunk, relevance_score)
            base_score = _calibrated_final_score(
                chunk,
                reliability_score=reliability_score,
                relevance_score=relevance_score,
                recency_score=recency_score,
            )
            adjustment_delta, adjustment_notes = _score_adjustments(
                chunk=chunk,
                source_type=normalized_source_type,
                relevance_score=relevance_score,
                recency_score=recency_score,
                fingerprint_counts=fingerprint_counts,
            )
            final_source_score = round(_clamp01(base_score + adjustment_delta), 4)
            enriched_chunk = dict(chunk)
            enriched_chunk["source_type"] = normalized_source_type
            enriched_chunk["reliability_score"] = round(reliability_score, 4)
            enriched_chunk["relevance_score"] = round(relevance_score, 4)
            enriched_chunk["recency_score"] = round(recency_score, 4)
            enriched_chunk["final_source_score"] = final_source_score
            enriched_chunk["ranking_adjustments"] = adjustment_notes
            enriched_chunk["reason"] = _build_reason(
                source_type=normalized_source_type,
                reliability_score=reliability_score,
                relevance_score=relevance_score,
                recency_score=recency_score,
                final_source_score=final_source_score,
                search_signal_score=_search_signal_score(chunk),
                adjustments=adjustment_notes,
            )
            enriched.append(enriched_chunk)

        ranked = sorted(
            enriched,
            key=lambda chunk: (
                _to_float(chunk.get("final_source_score")) or 0.0,
                _to_float(chunk.get("reliability_score")) or 0.0,
                _to_float(chunk.get("relevance_score")) or 0.0,
                -(_to_int(chunk.get("rank")) or 999),
            ),
            reverse=True,
        )[:25]

        for idx, item in enumerate(ranked, start=1):
            item["rank"] = idx

        warning_parts = [str(state.get("warning") or "").strip()]
        if llm_warning:
            warning_parts.append(llm_warning)
        return {
            "ranked_sources": ranked,
            "warning": " | ".join(part for part in warning_parts if part) or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "ranked_sources": state.get("ranked_sources"),
            "warning": f"source_ranker fallback: {exc}",
            "error": None,
        }
