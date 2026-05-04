from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_PRICE_OPINION_MARKERS: tuple[str, ...] = (
    "buy",
    "sell",
    "target price",
    "price target",
    "upside",
    "downside",
    "overvalued",
    "undervalued",
)
_SPECULATION_MARKERS: tuple[str, ...] = (
    "could",
    "might",
    "maybe",
    "possibly",
    "likely",
    "unlikely",
    "rumor",
    "rumour",
)
_PROMOTIONAL_MARKERS: tuple[str, ...] = (
    "sponsored",
    "partner content",
    "affiliate",
    "promoted",
)
_NUMERIC_RE = re.compile(r"\d")

_USED_FOR_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "what_changed",
        ("yoy", "qoq", "increased", "decreased", "declined", "rose", "fell", "guidance"),
    ),
    (
        "what_matters_now",
        ("demand", "margin", "guidance", "risk", "cash flow", "backlog", "headwind"),
    ),
    ("bull_points", ("beat", "strong", "growth", "expansion", "improved", "accelerat")),
    ("bear_points", ("miss", "weak", "decline", "pressure", "slowdown", "risk", "headwind")),
    (
        "what_to_watch_next",
        ("next quarter", "outlook", "watch", "monitor", "going forward", "expects"),
    ),
)

_STRENGTH_SCORE: dict[str, float] = {
    "strong": 1.00,
    "medium": 0.70,
    "weak": 0.35,
}
_OFFICIAL_SUPPORT_SOURCE_TYPES: set[str] = {
    "sec_filing",
    "earnings_release",
    "company_presentation",
    "company_ir_page",
    "public:sec_edgar",
    "public:company_ir",
}

_BEAR_MARKERS: tuple[str, ...] = (
    "risk",
    "headwind",
    "pressure",
    "decline",
    "decreased",
    "down",
    "slowed",
    "slowdown",
    "weaker",
    "miss",
    "shortfall",
    "competition",
    "competitive",
    "regulat",
    "export",
    "restriction",
    "constraint",
    "lawsuit",
    "litigation",
    "impairment",
    "restructur",
    "charge",
    "inventory",
    "write-down",
    "writeoff",
    "supply",
    "concentration",
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalized_text(ev: dict[str, Any]) -> str:
    return str(ev.get("claim") or ev.get("text") or "").strip()


def _reporting_relevance_score(ev: dict[str, Any], text: str) -> float:
    period = str(ev.get("period") or "").strip().lower()
    comparison_type = str(ev.get("comparison_type") or "").strip().lower()
    metric = str(ev.get("metric") or "").strip().lower()
    source_type = str(ev.get("source_type") or "").strip().lower()
    lower_text = text.lower()

    score = 0.35
    if period in {"latest_quarter"} or "q" in period:
        score += 0.25
    if comparison_type in {"yoy", "qoq", "guidance_change", "narrative_change"}:
        score += 0.20
    if metric in {
        "revenue_growth",
        "eps_profit_change",
        "margin",
        "guidance",
        "segment_performance",
        "demand_signal",
        "cost_capex_signal",
        "risk_disclosure",
        "market_reaction",
    }:
        score += 0.15
    if _contains_any(lower_text, ("latest", "this quarter", "reported", "results", "earnings")):
        score += 0.15
    if source_type in {"sec_filing", "earnings_release", "earnings_call_transcript"}:
        score += 0.10
    return round(min(1.0, score), 4)


def _infer_used_for(text: str) -> list[str]:
    lower = text.lower()
    used_for: list[str] = []
    for label, markers in _USED_FOR_MARKERS:
        if _contains_any(lower, markers):
            used_for.append(label)
    return used_for or ["what_matters_now"]


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


def _should_exclude(ev: dict[str, Any], text: str) -> str | None:
    lower = text.lower()
    if not text:
        return "Empty evidence claim."
    if len(text) < 20:
        return "Too short/generic to be useful."
    if _contains_any(lower, _PRICE_OPINION_MARKERS):
        return "Contains buy/sell or price-target style advice."
    if _contains_any(lower, _PROMOTIONAL_MARKERS):
        return "Promotional/affiliate style content."

    source_type = str(ev.get("source_type") or "").strip().lower()
    strength = str(ev.get("evidence_strength") or "").strip().lower()
    fact_or_interpretation = str(ev.get("fact_or_interpretation") or "").strip().lower()
    has_numeric = _NUMERIC_RE.search(text) is not None

    if (
        strength == "weak"
        and fact_or_interpretation == "interpretation"
        and _contains_any(lower, _SPECULATION_MARKERS)
    ):
        return "Weak speculative interpretation without supporting reporting."
    if (
        source_type in {"analyst_or_commentary", "public:analyst_or_commentary"}
        and not has_numeric
        and strength == "weak"
    ):
        return "Unsupported commentary without verifiable signal."
    return None


def _hard_guard_interpretation(
    ev: dict[str, Any],
    text: str,
) -> tuple[bool, float, str | None]:
    """
    Hard pre-synthesis quality gate:
    - Exclude weak interpretations without numeric or official support.
    - Down-rank medium/strong interpretations that still lack numeric+official backing.
    """
    fact_or_interpretation = str(ev.get("fact_or_interpretation") or "").strip().lower()
    if fact_or_interpretation != "interpretation":
        return (False, 0.0, None)

    source_type = str(ev.get("source_type") or "").strip().lower()
    strength = str(ev.get("evidence_strength") or "").strip().lower()
    has_numeric = _NUMERIC_RE.search(text) is not None
    has_official_support = source_type in _OFFICIAL_SUPPORT_SOURCE_TYPES

    if has_numeric or has_official_support:
        return (False, 0.0, None)

    if strength == "weak" or source_type in {"analyst_or_commentary", "public:analyst_or_commentary"}:
        return (
            True,
            0.0,
            "Hard guard: interpretation excluded (no numeric signal and no official source support).",
        )

    return (
        False,
        0.18,
        "Hard guard: interpretation down-ranked (missing numeric signal and official source support).",
    )


def _inclusion_score(ev: dict[str, Any], reporting_relevance_score: float) -> float:
    final_source_score_raw = ev.get("final_source_score")
    confidence_raw = ev.get("confidence")
    strength = str(ev.get("evidence_strength") or "").strip().lower()
    source_strength_score = _STRENGTH_SCORE.get(strength, 0.35)

    try:
        final_source_score = (
            float(final_source_score_raw) if final_source_score_raw is not None else 0.5
        )
    except Exception:
        final_source_score = 0.5
    try:
        confidence = float(confidence_raw) if confidence_raw is not None else 0.65
    except Exception:
        confidence = 0.65

    # If source score is missing, fallback to confidence to avoid over-penalizing.
    blended_source_score = (0.7 * final_source_score) + (0.3 * confidence)

    score = (
        (0.45 * blended_source_score)
        + (0.35 * source_strength_score)
        + (0.20 * reporting_relevance_score)
    )
    return round(min(1.0, max(0.0, score)), 4)


def _needs_bear_coverage(selected: list[dict[str, Any]]) -> bool:
    bear_count = 0
    for ev in selected:
        used_for = _as_list(ev.get("used_for"))
        if "bear_points" in used_for:
            bear_count += 1
    return bear_count < 2


def _bear_mode_candidates(classified: list[object], already_selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_keys: set[str] = set()
    for ev in already_selected:
        claim = _normalized_text(ev).lower()
        source_url = str(ev.get("source_url") or ev.get("source") or "").strip().lower()
        if claim and source_url:
            selected_keys.add(f"{claim}||{source_url}")

    candidates: list[dict[str, Any]] = []
    for raw in classified:
        if not isinstance(raw, dict):
            continue
        ev = dict(raw)
        claim = _normalized_text(ev)
        if not claim:
            continue
        source_url = str(ev.get("source_url") or ev.get("source") or "").strip()
        key = f"{claim.lower()}||{source_url.lower()}"
        if key in selected_keys:
            continue

        strength = str(ev.get("evidence_strength") or "").strip().lower()
        if strength not in {"strong", "medium"}:
            continue

        source_type = str(ev.get("source_type") or "").strip().lower()
        lower_claim = claim.lower()

        # Bear mode focuses on negatives/risk from reliable sources.
        has_bear_signal = _contains_any(lower_claim, _BEAR_MARKERS) or str(ev.get("category") or "").strip().lower() in {
            "risk_disclosure",
            "market_reaction",
        }
        if not has_bear_signal:
            continue

        official_like = source_type in _OFFICIAL_SUPPORT_SOURCE_TYPES or source_type in {
            "earnings_call_transcript",
            "reputable_financial_news",
        }
        if not official_like:
            continue

        # Conservative: treat these as bear_points only; keep provenance and labels.
        ev["used_for"] = ["bear_points"]
        ev["bear_mode"] = True
        candidates.append(ev)

    candidates = sorted(
        candidates,
        key=lambda item: (
            float(item.get("confidence") or 0.0),
            float(item.get("final_source_score") or 0.0),
        ),
        reverse=True,
    )
    return candidates


def _llm_selection_decisions(classified: list[object]) -> dict[int, dict[str, Any]]:
    payload_evidences: list[dict[str, Any]] = []
    for idx, raw in enumerate(classified):
        if not isinstance(raw, dict):
            continue
        ev = raw
        payload_evidences.append(
            {
                "idx": idx,
                "claim": _normalized_text(ev),
                "source_url": str(ev.get("source_url") or ev.get("source") or "").strip(),
                "source_type": str(ev.get("source_type") or "").strip(),
                "evidence_strength": str(ev.get("evidence_strength") or "").strip(),
                "fact_or_interpretation": str(ev.get("fact_or_interpretation") or "").strip(),
                "confidence": ev.get("confidence"),
                "final_source_score": ev.get("final_source_score"),
            }
        )

    result = invoke_prompt_json(
        prompt_filename="evidence_selector.md",
        payload={"evidences": payload_evidences},
        output_schema_hint="""
{
  "decisions": [
    {
      "idx": 0,
      "include": true,
      "reason": "string",
      "inclusion_score": 0.0,
      "used_for": [
        "what_changed",
        "what_matters_now",
        "bull_points",
        "bear_points",
        "what_to_watch_next"
      ]
    }
  ]
}
""".strip(),
    )

    raw_decisions = result.get("decisions") if isinstance(result, dict) else None
    if not isinstance(raw_decisions, list):
        return {}

    out: dict[int, dict[str, Any]] = {}
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if not isinstance(idx, int | float | str):
            continue
        try:
            i = int(idx)
        except Exception:
            continue
        if i < 0 or i >= len(classified) or i in out:
            continue
        used_for_raw = item.get("used_for")
        used_for: list[str] = []
        if isinstance(used_for_raw, list):
            for tag in used_for_raw:
                tag_s = str(tag).strip()
                if tag_s:
                    used_for.append(tag_s)
        inclusion_score_raw = item.get("inclusion_score")
        if not isinstance(inclusion_score_raw, int | float | str):
            inclusion_score_raw = 0.0
        try:
            inclusion_score = float(inclusion_score_raw)
        except Exception:
            inclusion_score = 0.0
        out[i] = {
            "include": bool(item.get("include")),
            "reason": str(item.get("reason") or "").strip(),
            "inclusion_score": round(min(1.0, max(0.0, inclusion_score)), 4),
            "used_for": used_for or ["what_matters_now"],
        }
    return out


@observe(name="agents.graph.nodes.evidence_selector.evidence_selector_node")
def evidence_selector_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Decide what evidence is worth including in the final brief.

    Output:
    - selected_evidences: list[dict]
    - discarded_evidence: list[dict]
    """
    try:
        classified = state.get("classified_evidences")
        if not isinstance(classified, list) or not classified:
            return {
                "selected_evidences": [],
                "selected_evidence": [],
                "discarded_evidence": [],
                "warning": state.get("warning"),
                "error": None,
            }

        seen_keys: set[str] = set()
        selected: list[dict[str, Any]] = []
        discarded: list[dict[str, Any]] = []

        llm_warning: str | None = None
        llm_decisions: dict[int, dict[str, Any]] = {}
        try:
            llm_decisions = _llm_selection_decisions(classified)
        except Exception as exc:
            llm_warning = f"evidence_selector LLM fallback: {exc}"

        for idx, raw in enumerate(classified):
            if not isinstance(raw, dict):
                continue
            ev = dict(raw)
            claim = _normalized_text(ev)
            source_url = str(ev.get("source_url") or ev.get("source") or "").strip().lower()
            dedupe_key = f"{claim.lower()}||{source_url}"
            if dedupe_key in seen_keys:
                ev["include"] = False
                ev["reason"] = "Duplicate evidence item."
                ev["inclusion_score"] = 0.0
                discarded.append(ev)
                continue
            seen_keys.add(dedupe_key)

            guard_exclude, guard_penalty, guard_reason = _hard_guard_interpretation(ev, claim)
            if guard_exclude:
                ev["include"] = False
                ev["reason"] = guard_reason
                ev["inclusion_score"] = 0.0
                ev["quality_gate"] = "hard_guard_excluded"
                discarded.append(ev)
                continue

            llm_item = llm_decisions.get(idx)
            if llm_item is not None:
                llm_score = float(llm_item.get("inclusion_score") or 0.0)
                adjusted_score = max(0.0, llm_score - guard_penalty)
                include = bool(llm_item.get("include")) and adjusted_score >= 0.62
                ev["include"] = include
                base_reason = str(llm_item.get("reason") or "").strip() or (
                    "Included by prompt-driven selection."
                    if include
                    else "Excluded by prompt-driven selection."
                )
                if guard_reason:
                    base_reason = f"{base_reason} {guard_reason}"
                ev["reason"] = base_reason
                ev["inclusion_score"] = round(adjusted_score, 4)
                ev["used_for"] = llm_item.get("used_for") or ["what_matters_now"]
                if guard_penalty > 0:
                    ev["quality_gate"] = "hard_guard_penalty"
                if include:
                    selected.append(ev)
                else:
                    discarded.append(ev)
                continue

            exclusion_reason = _should_exclude(ev, claim)
            if exclusion_reason:
                ev["include"] = False
                ev["reason"] = exclusion_reason
                ev["inclusion_score"] = 0.0
                discarded.append(ev)
                continue

            reporting_score = _reporting_relevance_score(ev, claim)
            inclusion_score = max(0.0, _inclusion_score(ev, reporting_score) - guard_penalty)
            used_for = _infer_used_for(claim)
            strength = str(ev.get("evidence_strength") or "").strip().lower()
            fact_or_interpretation = str(ev.get("fact_or_interpretation") or "").strip().lower()

            include = inclusion_score >= 0.62 and strength in {"strong", "medium"}
            if strength == "weak":
                # Weak evidence can be included only when it helps explain
                # market debate and is clearly labeled weak.
                include = (
                    inclusion_score >= 0.58
                    and fact_or_interpretation == "interpretation"
                    and any(
                        tag in used_for
                        for tag in ("bull_points", "bear_points", "what_matters_now")
                    )
                )

            ev["inclusion_score"] = inclusion_score
            ev["used_for"] = used_for
            ev["include"] = include
            if guard_penalty > 0:
                ev["quality_gate"] = "hard_guard_penalty"
            if include:
                ev["reason"] = (
                    "Included: relevant to latest reporting "
                    f"score={inclusion_score:.2f}."
                )
                if guard_reason:
                    ev["reason"] += f" {guard_reason}"
                selected.append(ev)
            else:
                ev["reason"] = (
                    f"Excluded: below threshold score={inclusion_score:.2f} "
                    "or low evidence utility."
                )
                if guard_reason:
                    ev["reason"] += f" {guard_reason}"
                discarded.append(ev)

        selected_sorted = sorted(
            selected,
            key=lambda item: (
                float(item.get("inclusion_score") or 0.0),
                float(item.get("confidence") or 0.0),
            ),
            reverse=True,
        )[:16]

        # Bear mode: ensure at least a couple of well-grounded bear points make it through.
        if _needs_bear_coverage(selected_sorted):
            for candidate in _bear_mode_candidates(classified, already_selected=selected_sorted)[:3]:
                candidate = dict(candidate)
                candidate["include"] = True
                candidate["inclusion_score"] = max(0.62, float(candidate.get("inclusion_score") or 0.62))
                candidate["reason"] = (
                    "Included (bear mode): ensures negative/risk coverage from reliable reporting."
                )
                selected_sorted.append(candidate)

            # Re-sort and cap after injections.
            selected_sorted = sorted(
                selected_sorted,
                key=lambda item: (
                    float(item.get("inclusion_score") or 0.0),
                    float(item.get("confidence") or 0.0),
                ),
                reverse=True,
            )[:16]

        discarded_sorted = sorted(
            discarded,
            key=lambda item: float(item.get("inclusion_score") or 0.0),
        )

        return {
            "selected_evidences": selected_sorted,
            "selected_evidence": selected_sorted,
            "discarded_evidence": discarded_sorted,
            "warning": " | ".join(
                part for part in [str(state.get("warning") or "").strip(), llm_warning] if part
            )
            or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "selected_evidences": state.get("selected_evidences"),
            "selected_evidence": state.get("selected_evidences"),
            "discarded_evidence": state.get("discarded_evidence"),
            "warning": f"evidence_selector fallback: {exc}",
            "error": None,
        }
