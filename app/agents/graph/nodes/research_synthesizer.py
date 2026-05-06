from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_DISCLAIMER = "This is not investment advice."
_SCOPE_NOTE = "Prototype scope: this iteration focuses on the Magnificent 7 stocks only."
_MAX_SECTION_ITEMS = 5
_TARGET_SECTION_ITEMS = 3
_EVIDENCE_STRENGTH_RUBRIC: list[str] = [
    (
        "strong = primary/official source (SEC filing, earnings release, company IR) + "
        "verifiable statement (often numbers or direct quotation)."
    ),
    (
        "medium = credible but more interpretative source "
        "(e.g. earnings call transcript, reputable financial news) "
        "or quantitative statement from a non-official source."
    ),
    (
        "weak = comment/sentiment/speculation (analyst/blog/social). "
    ),
]
_CHANGED_MARKERS: tuple[str, ...] = (
    "yoy",
    "year over year",
    "year-over-year",
    "qoq",
    "quarter over quarter",
    "sequential",
    "reported",
    "results",
    "revenue",
    "eps",
)
_MATTERS_MARKERS: tuple[str, ...] = (
    "margin",
    "guidance",
    "demand",
    "headwind",
    "risk",
    "cash flow",
    "backlog",
    "capex",
    "inventory",
)
_BULL_MARKERS: tuple[str, ...] = (
    "backlog",
    "beat",
    "cash flow",
    "cloud",
    "demand",
    "expansion",
    "gain",
    "grew",
    "growth",
    "higher",
    "improv",
    "increased",
    "margin expansion",
    "positive",
    "raised",
    "record",
    "rose",
    "solid",
    "accelerat",
    "strong",
)
_BEAR_MARKERS: tuple[str, ...] = (
    "competition",
    "competitive",
    "concern",
    "constraint",
    "deceleration",
    "declined",
    "decline",
    "decrease",
    "down",
    "drop",
    "fell",
    "headwind",
    "litigation",
    "lower",
    "miss",
    "pressure",
    "regulat",
    "restriction",
    "risk",
    "shortfall",
    "slowed",
    "slowdown",
    "tariff",
    "weak",
    "weaker",
)
_WATCH_MARKERS: tuple[str, ...] = (
    "guidance",
    "outlook",
    "next quarter",
    "watch",
    "monitor",
    "forward",
    "expects",
)
_SECTOR_MARKERS: dict[str, tuple[str, ...]] = {
    "information technology": (
        "cloud",
        "ai",
        "semiconductor",
        "gpu",
        "capex",
        "pricing",
        "inventory",
        "utilization",
    ),
    "communication services": (
        "ad spend",
        "advertising",
        "engagement",
        "monetization",
        "regulat",
        "traffic acquisition",
    ),
    "consumer discretionary": (
        "consumer demand",
        "unit growth",
        "average selling price",
        "discount",
        "auto",
        "ev",
        "delivery",
    ),
}
_MAG7_TAIL_RISKS: dict[str, tuple[str, ...]] = {
    "AAPL": (
        "Scenario risk: iPhone replacement cycles or China demand could weaken, "
        "pressuring revenue growth and hardware margins.",
        "Scenario risk: regulatory or platform-fee pressure could reduce App Store economics.",
    ),
    "AMZN": (
        "Scenario risk: retail margin gains could reverse if fulfillment costs, "
        "wage pressure, or discounting rise.",
        "Scenario risk: AWS growth could slow if cloud optimization or "
        "AI infrastructure competition weighs on demand.",
    ),
    "GOOG": (
        "Scenario risk: search and YouTube monetization could face pressure from "
        "AI-driven changes in user behavior and ad budgets.",
        "Scenario risk: antitrust remedies or privacy regulation could constrain "
        "distribution, data use, or advertising economics.",
    ),
    "GOOGL": (
        "Scenario risk: search and YouTube monetization could face pressure from "
        "AI-driven changes in user behavior and ad budgets.",
        "Scenario risk: antitrust remedies or privacy regulation could constrain "
        "distribution, data use, or advertising economics.",
    ),
    "META": (
        "Scenario risk: ad demand, engagement, or monetization could soften if "
        "macro conditions or competition pressure advertiser spend.",
        "Scenario risk: regulatory scrutiny around privacy, AI, or platform content "
        "could raise costs or limit targeting efficiency.",
    ),
    "MSFT": (
        "Scenario risk: Azure and AI infrastructure growth could disappoint if "
        "enterprise demand slows or cloud optimization returns.",
        "Scenario risk: AI capex could pressure free cash flow or margins if "
        "monetization lags infrastructure spending.",
    ),
    "NVDA": (
        "Scenario risk: data center GPU demand could normalize if hyperscaler "
        "AI capex slows or customers digest prior purchases.",
        "Scenario risk: export restrictions, supply constraints, or competitive "
        "accelerators could pressure revenue growth and margins.",
    ),
    "TSLA": (
        "Scenario risk: EV demand or pricing could weaken if competition, incentives, "
        "or consumer affordability pressure deliveries.",
        "Scenario risk: margin recovery could disappoint if price cuts, "
        "factory utilization, or launch costs offset cost reductions.",
    ),
}
_SECTOR_TAIL_RISKS: dict[str, tuple[str, ...]] = {
    "information technology": (
        "Scenario risk: technology demand could slow if enterprise budgets tighten "
        "or customers delay upgrades.",
        "Scenario risk: AI and cloud infrastructure spending could pressure margins "
        "if monetization lags investment.",
    ),
    "communication services": (
        "Scenario risk: advertising or engagement trends could weaken if macro "
        "conditions or platform competition pressure user activity.",
        "Scenario risk: regulatory scrutiny could raise compliance costs or "
        "constrain data-driven monetization.",
    ),
    "consumer discretionary": (
        "Scenario risk: consumer demand could soften if affordability, rates, "
        "or competition pressure unit growth.",
        "Scenario risk: margin recovery could disappoint if pricing, incentives, "
        "or fulfillment costs move against the company.",
    ),
}


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
        "source_type": str(ev.get("source_type") or "").strip() or None,
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
        point["type"] = _normalize_point_type(
            item.get("type") or item.get("fact_or_interpretation")
        )
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


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _matters_markers_for_context(sector: str, industry: str) -> tuple[str, ...]:
    sector_key = sector.strip().lower()
    industry_key = industry.strip().lower()
    extra: list[str] = []
    if sector_key in _SECTOR_MARKERS:
        extra.extend(_SECTOR_MARKERS[sector_key])
    for key, values in _SECTOR_MARKERS.items():
        if key and key in industry_key:
            extra.extend(values)
    merged = [*_MATTERS_MARKERS, *extra]
    deduped: list[str] = []
    seen: set[str] = set()
    for marker in merged:
        m = marker.strip().lower()
        if not m or m in seen:
            continue
        seen.add(m)
        deduped.append(m)
    return tuple(deduped)


def _point_key(point: dict[str, Any]) -> str:
    evidence_id = str(point.get("evidence_id") or "").strip().lower()
    if evidence_id:
        return evidence_id
    text = str(point.get("text") or "").strip().lower()
    source = str(point.get("source_url") or "").strip().lower()
    return f"{text}||{source}"


def _is_bear_point(point: dict[str, Any]) -> bool:
    text = str(point.get("text") or "").strip().lower()
    return _contains_any(text, _BEAR_MARKERS)


def _is_bull_point(point: dict[str, Any]) -> bool:
    text = str(point.get("text") or "").strip().lower()
    return _contains_any(text, _BULL_MARKERS) and not _is_bear_point(point)


def _scenario_bear_points(
    *,
    symbol: str,
    sector: str,
    industry: str,
) -> list[dict[str, Any]]:
    templates = _MAG7_TAIL_RISKS.get(symbol.strip().upper())
    if templates is None:
        sector_key = sector.strip().lower()
        templates = _SECTOR_TAIL_RISKS.get(sector_key)
    if templates is None and industry:
        industry_key = industry.strip().lower()
        for sector_key, sector_templates in _SECTOR_TAIL_RISKS.items():
            if sector_key in industry_key:
                templates = sector_templates
                break
    if templates is None:
        templates = (
            "Scenario risk: demand, margins, or execution could deteriorate "
            "relative to current investor expectations.",
        )

    return [
        {
            "text": text,
            "type": "interpretation",
            "evidence_strength": "weak",
            "evidence_id": None,
            "source_url": None,
            "source_type": "scenario_risk",
        }
        for text in templates
    ]


def _section_candidates(
    *,
    primary: list[dict[str, Any]],
    ranked_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _dedupe_points([*primary, *ranked_points])


def _pick_section_points(
    *,
    primary: list[dict[str, Any]],
    ranked_points: list[dict[str, Any]],
    seen: set[str],
    want: int,
    markers: tuple[str, ...] | None = None,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    allow_fallback: bool = True,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    candidates = _section_candidates(primary=primary, ranked_points=ranked_points)

    def _accept(point: dict[str, Any], *, require_markers: bool) -> bool:
        key = _point_key(point)
        if not key or key in seen:
            return False
        if predicate is not None and not predicate(point):
            return False
        if require_markers and markers is not None:
            text = str(point.get("text") or "").strip().lower()
            if not _contains_any(text, markers):
                return False
        return True

    if markers is not None:
        for point in candidates:
            if not _accept(point, require_markers=True):
                continue
            out.append(point)
            seen.add(_point_key(point))
            if len(out) >= want:
                return out

    if not allow_fallback:
        return out

    for point in candidates:
        if not _accept(point, require_markers=False):
            continue
        out.append(point)
        seen.add(_point_key(point))
        if len(out) >= want:
            break
    return out


def _pick_reuse_points(
    *,
    primary: list[dict[str, Any]],
    ranked_points: list[dict[str, Any]],
    avoid: set[str],
    want: int,
    markers: tuple[str, ...] | None = None,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    local_seen: set[str] = set()
    candidates = _section_candidates(primary=primary, ranked_points=ranked_points)

    def _maybe_append(point: dict[str, Any], *, avoid_keys: bool, require_markers: bool) -> bool:
        key = _point_key(point)
        if not key or key in local_seen:
            return False
        if avoid_keys and key in avoid:
            return False
        if predicate is not None and not predicate(point):
            return False
        if require_markers and markers is not None:
            text = str(point.get("text") or "").strip().lower()
            if not _contains_any(text, markers):
                return False
        local_seen.add(key)
        out.append(point)
        return len(out) >= want

    for avoid_keys in (True, False):
        for require_markers in (True, False):
            if markers is None and require_markers:
                continue
            for point in candidates:
                if _maybe_append(point, avoid_keys=avoid_keys, require_markers=require_markers):
                    return out
    return out


def _render_point(point: dict[str, Any]) -> str:
    text = str(point.get("text") or "").strip()
    if not text:
        return ""
    point_type = _normalize_point_type(point.get("type"))
    strength = _normalize_strength(point.get("evidence_strength")) or "unknown"
    evidence_id = str(point.get("evidence_id") or "").strip()
    source_url = str(point.get("source_url") or "").strip()
    source_type = str(point.get("source_type") or "").strip().lower()
    evidence_label = f"[evidence:{evidence_id}] " if evidence_id else ""
    source_type_label = f" [{source_type}]" if source_type else ""
    source_label = f" ({source_url})" if source_url else ""
    return (
        f"{evidence_label}[{point_type.upper()} | {strength}]"
        f"{source_type_label} {text}{source_label}"
    )


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
    sector: str,
    industry: str,
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    payload_evidences: list[dict[str, Any]] = []
    for ev in selected[:24]:
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
            "sector": sector or None,
            "industry": industry or None,
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
        sector = str(state.get("sector") or "").strip()
        industry = str(state.get("industry") or "").strip()

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
        ranked_sources_raw = state.get("ranked_sources")
        ranked_sources_kept: int | str = (
            len(ranked_sources_raw) if isinstance(ranked_sources_raw, list) else "N/A"
        )
        workflow_trace: list[str] = [
            f"Resolved entity: {company_name or 'Unknown'} ({symbol or 'N/A'})",
            (
                "Searched public sources and ranked them by "
                f"reliability/relevance/recency; kept top {ranked_sources_kept}."
            ),
            (
                "Extracted evidence items from ranked sources; "
                "classified strength (strong/medium/weak) and fact vs interpretation."
            ),
            (
                "Selected evidence with strict grounding "
                "(evidence-based bullets map to evidence_id + source_url) "
                "and coverage across sections."
            ),
            (
                "Bear mode: ensured at least 2 risk/negative points are included "
                "when available from reliable sources."
            ),
        ]
        if sector or industry:
            context_label = " / ".join(part for part in [sector, industry] if part)
            workflow_trace.append(f"Sector context applied: {context_label}.")

        llm_warning: str | None = None
        llm_sections: dict[str, Any] = {}
        try:
            llm_sections = _llm_synthesize_sections(
                company_name=company_name,
                symbol=symbol,
                sector=sector,
                industry=industry,
                selected=ranked,
            )
        except TimeoutError:
            # Expected degradation path: the deterministic renderer below produces a usable brief.
            llm_warning = None
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

        ranked_points = _points_from_evidences(ranked)
        what_changed_primary = _dedupe_points(
            [*what_changed, *_points_from_evidences(buckets["what_changed"])]
        )
        what_matters_primary = _dedupe_points(
            [*what_matters, *_points_from_evidences(buckets["what_matters_now"])]
        )
        bull_primary = _dedupe_points(
            [*bull_points, *_points_from_evidences(buckets["bull_points"])]
        )
        bear_primary = _dedupe_points(
            [*bear_points, *_points_from_evidences(buckets["bear_points"])]
        )
        watch_primary = _dedupe_points(
            [*watch_next, *_points_from_evidences(buckets["what_to_watch_next"])]
        )

        seen_keys: set[str] = set()
        matters_markers = _matters_markers_for_context(sector=sector, industry=industry)
        what_changed = _pick_section_points(
            primary=what_changed_primary,
            ranked_points=ranked_points,
            seen=seen_keys,
            want=_TARGET_SECTION_ITEMS,
            markers=_CHANGED_MARKERS,
            allow_fallback=False,
        )
        what_matters = _pick_section_points(
            primary=what_matters_primary,
            ranked_points=ranked_points,
            seen=seen_keys,
            want=_TARGET_SECTION_ITEMS,
            markers=matters_markers,
            allow_fallback=True,
        )
        bull_points = _pick_section_points(
            primary=bull_primary,
            ranked_points=ranked_points,
            seen=seen_keys,
            want=_TARGET_SECTION_ITEMS,
            markers=_BULL_MARKERS,
            predicate=_is_bull_point,
            allow_fallback=True,
        )
        # Bear points should stay genuinely risk-oriented.
        bear_points = _pick_section_points(
            primary=bear_primary,
            ranked_points=ranked_points,
            seen=seen_keys,
            want=_TARGET_SECTION_ITEMS,
            markers=_BEAR_MARKERS,
            predicate=_is_bear_point,
            allow_fallback=True,
        )
        watch_next = _pick_section_points(
            primary=watch_primary,
            ranked_points=ranked_points,
            seen=seen_keys,
            want=_TARGET_SECTION_ITEMS,
            markers=_WATCH_MARKERS,
            allow_fallback=True,
        )
        if not bull_points:
            bull_points = _pick_reuse_points(
                primary=bull_primary,
                ranked_points=ranked_points,
                avoid={
                    _point_key(point)
                    for section in (what_changed, what_matters, bear_points, watch_next)
                    for point in section
                },
                want=2,
                markers=_BULL_MARKERS,
                predicate=_is_bull_point,
            )
        if not bear_points:
            bear_points = _pick_reuse_points(
                primary=bear_primary,
                ranked_points=ranked_points,
                avoid={
                    _point_key(point)
                    for section in (what_changed, what_matters, bull_points, watch_next)
                    for point in section
                },
                want=2,
                markers=_BEAR_MARKERS,
                predicate=_is_bear_point,
            )
        if not bear_points:
            bear_points = _scenario_bear_points(
                symbol=symbol,
                sector=sector,
                industry=industry,
            )
        if not watch_next:
            watch_next = _pick_reuse_points(
                primary=watch_primary,
                ranked_points=ranked_points,
                avoid={
                    _point_key(point)
                    for section in (what_changed, what_matters, bull_points, bear_points)
                    for point in section
                },
                want=2,
                markers=_WATCH_MARKERS,
            )

        disclaimer = str(llm_sections.get("disclaimer") or _DISCLAIMER).strip() or _DISCLAIMER
        if "magnificent 7" not in disclaimer.lower() and "mag 7" not in disclaimer.lower():
            disclaimer = f"{_SCOPE_NOTE} {disclaimer}".strip()

        lines: list[str] = [
            f"Company: {company_name or 'Unknown'}",
            f"Ticker: {symbol or 'N/A'}",
            "Scope: Magnificent 7 only",
            "",
            _render_text_section("0) Workflow trace (agent steps)", workflow_trace),
            "",
            _render_text_section("0b) Evidence strength rubric", _EVIDENCE_STRENGTH_RUBRIC),
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
            "workflow_trace": workflow_trace,
            "evidence_strength_rubric": _EVIDENCE_STRENGTH_RUBRIC,
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
