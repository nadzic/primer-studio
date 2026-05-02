from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_DISCLAIMER = "This is not investment advice."
_MAX_SECTION_ITEMS = 5


def _evidence_id(ev: dict[str, Any]) -> str:
    return str(ev.get("evidence_id") or "").strip()


def _source_url(ev: dict[str, Any]) -> str:
    return str(ev.get("source_url") or ev.get("source") or "").strip()


def _claim_text(ev: dict[str, Any]) -> str:
    return str(ev.get("claim") or ev.get("text") or "").strip()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    if value is None:
        return []
    s = str(value).strip()
    return [s] if s else []


def _normalize_point_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"fact", "interpretation"} else "interpretation"


def _normalize_strength(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"strong", "medium", "weak"} else None


def _dedupe_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for point in points:
        text = str(point.get("text") or "").strip()
        if not text:
            continue
        evidence_id = str(point.get("evidence_id") or "").strip().lower()
        source = str(point.get("source_url") or "").strip().lower()
        key = evidence_id or f"{text.lower()}||{source}"
        if key in seen:
            continue
        seen.add(key)
        out.append(point)
    return out


def _point_from_evidence(ev: dict[str, Any]) -> dict[str, Any] | None:
    text = _claim_text(ev)
    evidence_id = _evidence_id(ev)
    source_url = _source_url(ev)
    if not text:
        return None
    if not evidence_id or not source_url:
        # Strict grounding: every brief point must map to a concrete evidence item and source.
        return None
    point: dict[str, Any] = {
        "text": text,
        "evidence_id": evidence_id,
        "type": _normalize_point_type(ev.get("fact_or_interpretation")),
        "evidence_strength": _normalize_strength(ev.get("evidence_strength")),
        "source_url": source_url or None,
    }
    return point


def _points_from_evidences(evidences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for ev in evidences:
        point = _point_from_evidence(ev)
        if point is not None:
            points.append(point)
    return _dedupe_points(points)


def _build_grounding_index(
    evidences: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_claim_source: dict[str, dict[str, Any]] = {}
    for ev in evidences:
        evidence_id = _evidence_id(ev)
        claim = _claim_text(ev)
        source_url = _source_url(ev)
        if evidence_id:
            by_id[evidence_id] = ev
        if claim and source_url:
            by_claim_source[f"{claim.lower()}||{source_url.lower()}"] = ev
    return by_id, by_claim_source


def _point_from_item(
    item: Any,
    by_id: Mapping[str, dict[str, Any]],
    by_claim_source: Mapping[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if isinstance(item, dict):
        evidence_id = str(item.get("evidence_id") or "").strip()
        source_url = str(item.get("source_url") or item.get("source") or "").strip()
        text = str(item.get("text") or item.get("claim") or "").strip()
        grounded_ev = by_id.get(evidence_id) if evidence_id else None
        if grounded_ev is None and text and source_url:
            grounded_ev = by_claim_source.get(f"{text.lower()}||{source_url.lower()}")
        if grounded_ev is None:
            return None
        point = _point_from_evidence(grounded_ev)
        if point is None:
            return None
        point["type"] = _normalize_point_type(item.get("type") or item.get("fact_or_interpretation"))
        strength = _normalize_strength(item.get("evidence_strength"))
        if strength is not None:
            point["evidence_strength"] = strength
        return point

    # Strict grounding: ignore plain strings with no evidence mapping.
    return None


def _as_points(
    value: Any,
    by_id: Mapping[str, dict[str, Any]],
    by_claim_source: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    points: list[dict[str, Any]] = []
    for item in value:
        point = _point_from_item(item, by_id=by_id, by_claim_source=by_claim_source)
        if point is not None:
            points.append(point)
    return _dedupe_points(points)


def _quality_counts(selected: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"strong": 0, "medium": 0, "weak": 0}
    for ev in selected:
        strength = str(ev.get("evidence_strength") or "").strip().lower()
        if strength in counts:
            counts[strength] += 1
        else:
            counts["weak"] += 1
    return counts


def _unique_non_empty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _bucket_selected(selected: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "what_changed": [],
        "what_matters_now": [],
        "bull_points": [],
        "bear_points": [],
        "what_to_watch_next": [],
    }
    for ev in selected:
        used_for = _as_list(ev.get("used_for"))
        for tag in used_for:
            if tag in buckets:
                buckets[tag].append(ev)
    return buckets


def _sorted_by_inclusion(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        selected,
        key=lambda ev: (
            float(ev.get("inclusion_score") or 0.0),
            float(ev.get("confidence") or 0.0),
        ),
        reverse=True,
    )


def _render_point(point: dict[str, Any]) -> str:
    text = str(point.get("text") or "").strip()
    if not text:
        return ""
    point_type = _normalize_point_type(point.get("type"))
    strength = _normalize_strength(point.get("evidence_strength")) or "unknown"
    evidence_id = str(point.get("evidence_id") or "").strip()
    source_url = str(point.get("source_url") or "").strip()
    evidence_label = f"[evidence:{evidence_id}] " if evidence_id else ""
    source_label = f" ({source_url})" if source_url else ""
    return f"{evidence_label}[{point_type.upper()} | {strength}] {text}{source_label}"


def _render_section(title: str, points: list[dict[str, Any]]) -> str:
    rendered = [_render_point(point) for point in points]
    rendered = [item for item in rendered if item]
    if not rendered:
        return f"{title}\n- No high-confidence selected evidence."
    bullets = "\n".join(f"- {item}" for item in rendered[:_MAX_SECTION_ITEMS])
    return f"{title}\n{bullets}"


def _render_text_section(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}\n- No high-confidence selected evidence."
    bullets = "\n".join(f"- {item}" for item in items[:_MAX_SECTION_ITEMS])
    return f"{title}\n{bullets}"


def _format_citations(evidences: list[dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for ev in evidences:
        src = _source_url(ev)
        if src and src not in citations:
            citations.append(src)
    return citations


def _llm_synthesize_sections(
    company_name: str,
    symbol: str,
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    payload_evidences: list[dict[str, Any]] = []
    for ev in selected[:16]:
        payload_evidences.append(
            {
                "evidence_id": _evidence_id(ev),
                "claim": _claim_text(ev),
                "source_url": _source_url(ev),
                "source_type": str(ev.get("source_type") or "").strip(),
                "evidence_strength": str(ev.get("evidence_strength") or "").strip(),
                "fact_or_interpretation": str(ev.get("fact_or_interpretation") or "").strip(),
                "used_for": _as_list(ev.get("used_for")),
                "inclusion_score": ev.get("inclusion_score"),
            }
        )

    result = invoke_prompt_json(
        prompt_filename="research_synthesizer.md",
        payload={
            "company_name": company_name,
            "symbol": symbol,
            "selected_evidences": payload_evidences,
        },
        output_schema_hint="""
{
  "executive_summary": "string",
  "what_changed": [
    {
      "evidence_id": "string",
      "text": "string",
      "type": "fact|interpretation",
      "evidence_strength": "strong|medium|weak",
      "source_url": "string|null"
    }
  ],
  "what_matters_most_now": [
    {
      "evidence_id": "string",
      "text": "string",
      "type": "fact|interpretation",
      "evidence_strength": "strong|medium|weak",
      "source_url": "string|null"
    }
  ],
  "bull_points": [
    {
      "evidence_id": "string",
      "text": "string",
      "type": "fact|interpretation",
      "evidence_strength": "strong|medium|weak",
      "source_url": "string|null"
    }
  ],
  "bear_points": [
    {
      "evidence_id": "string",
      "text": "string",
      "type": "fact|interpretation",
      "evidence_strength": "strong|medium|weak",
      "source_url": "string|null"
    }
  ],
  "what_to_watch_next": [
    {
      "evidence_id": "string",
      "text": "string",
      "type": "fact|interpretation",
      "evidence_strength": "strong|medium|weak",
      "source_url": "string|null"
    }
  ],
  "source_notes": ["string"],
  "disclaimer": "string"
}
""".strip(),
    )
    return result if isinstance(result, dict) else {}


@observe(name="agents.graph.nodes.research_synthesizer.research_synthesizer_node")
def research_synthesizer_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Produce a concise structured brief using only selected evidences.

    Output:
    - research_summary: str | None
    - research_citations: list[str]
    """
    try:
        company_name = str(state.get("company_name") or "").strip()
        symbol = str(state.get("symbol") or "").strip().upper()

        selected = state.get("selected_evidences")
        if not isinstance(selected, list):
            selected = state.get("selected_evidence")
        if not isinstance(selected, list) or not selected:
            summary = f"No evidence found for {company_name or symbol or 'the query'}."
            return {
                "research_summary": summary,
                "research_citations": [],
                "warning": state.get("warning"),
                "error": None,
            }

        selected_dicts = [ev for ev in selected if isinstance(ev, dict)]
        ranked = _sorted_by_inclusion(selected_dicts)
        quality = _quality_counts(ranked)
        buckets = _bucket_selected(ranked)
        by_id, by_claim_source = _build_grounding_index(ranked)

        llm_warning: str | None = None
        llm_sections: dict[str, Any] = {}
        try:
            llm_sections = _llm_synthesize_sections(
                company_name=company_name, symbol=symbol, selected=ranked
            )
        except Exception as exc:
            llm_warning = f"research_synthesizer LLM fallback: {exc}"

        if llm_sections:
            executive_summary = str(llm_sections.get("executive_summary") or "").strip()
            what_changed = _as_points(
                llm_sections.get("what_changed"),
                by_id=by_id,
                by_claim_source=by_claim_source,
            )
            what_matters = _as_points(
                llm_sections.get("what_matters_most_now"),
                by_id=by_id,
                by_claim_source=by_claim_source,
            )
            bull_points = _as_points(
                llm_sections.get("bull_points"),
                by_id=by_id,
                by_claim_source=by_claim_source,
            )
            bear_points = _as_points(
                llm_sections.get("bear_points"),
                by_id=by_id,
                by_claim_source=by_claim_source,
            )
            watch_next = _as_points(
                llm_sections.get("what_to_watch_next"),
                by_id=by_id,
                by_claim_source=by_claim_source,
            )
            source_notes = _unique_non_empty(_as_list(llm_sections.get("source_notes")))
        else:
            executive_candidates = [
                _claim_text(ev)
                for ev in ranked
                if _claim_text(ev)
                and str(ev.get("evidence_strength") or "").strip().lower() in {"strong", "medium"}
            ][:2]
            if not executive_candidates:
                executive_candidates = [_claim_text(ev) for ev in ranked if _claim_text(ev)][:2]
            executive_summary = (
                "; ".join(executive_candidates)
                if executive_candidates
                else f"Selected evidence for {company_name or symbol or 'the query'} was limited."
            )

            what_changed = _points_from_evidences(buckets["what_changed"])
            what_matters = _points_from_evidences(buckets["what_matters_now"])
            bull_points = _points_from_evidences(buckets["bull_points"])
            bear_points = _points_from_evidences(buckets["bear_points"])
            watch_next = _points_from_evidences(buckets["what_to_watch_next"])
            source_notes = _unique_non_empty(
                [
                    f"{str(ev.get('source_type') or 'unknown').strip()}: {_source_url(ev)}"
                    for ev in ranked
                    if _source_url(ev)
                ]
            )

        if not executive_summary:
            executive_summary = (
                f"Selected evidence for {company_name or symbol or 'the query'} was limited."
            )
        if not what_changed:
            what_changed = _points_from_evidences(ranked[:2])
        if not what_matters:
            what_matters = _points_from_evidences(ranked[2:4])

        disclaimer = str(llm_sections.get("disclaimer") or _DISCLAIMER).strip() or _DISCLAIMER

        lines: list[str] = [
            f"Company: {company_name or 'Unknown'}",
            f"Ticker: {symbol or 'N/A'}",
            "",
            _render_text_section("1) Executive summary", [executive_summary]),
            "",
            _render_section("2) What changed in the latest results / reporting", what_changed),
            "",
            _render_section("3) What matters most now", what_matters),
            "",
            _render_section("4) Main bull points", bull_points),
            "",
            _render_section("5) Main bear points", bear_points),
            "",
            _render_section("6) What to watch next", watch_next),
            "",
            "7) Evidence quality summary",
            f"- strong: {quality['strong']}",
            f"- medium: {quality['medium']}",
            f"- weak: {quality['weak']} (clearly labeled when used)",
            "",
            _render_text_section("8) Source notes", source_notes),
            "",
            "9) Disclaimer",
            f"- {disclaimer}",
        ]

        summary = "\n".join(lines).strip() or None
        research_brief: dict[str, Any] = {
            "company": company_name or None,
            "ticker": symbol or None,
            "reporting_context": "Latest available reporting context from selected evidence.",
            "executive_summary": executive_summary,
            "what_changed": what_changed[:_MAX_SECTION_ITEMS],
            "what_matters_most_now": what_matters[:_MAX_SECTION_ITEMS],
            "bull_points": bull_points[:_MAX_SECTION_ITEMS],
            "bear_points": bear_points[:_MAX_SECTION_ITEMS],
            "what_to_watch_next": watch_next[:_MAX_SECTION_ITEMS],
            "evidence_quality_summary": quality,
            "source_notes": source_notes[:8],
            "disclaimer": disclaimer,
        }

        return {
            "research_summary": summary,
            "research_brief": research_brief,
            "research_citations": _format_citations(ranked),
            "warning": " | ".join(
                part for part in [str(state.get("warning") or "").strip(), llm_warning] if part
            )
            or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "research_summary": state.get("research_summary"),
            "research_brief": state.get("research_brief"),
            "research_citations": state.get("research_citations"),
            "warning": f"research_synthesizer fallback: {exc}",
            "error": None,
        }
