from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.agents.services.prompt_llm_service import invoke_prompt_json
from app.observability.tracing import observe

_NUMERIC_RE = re.compile(
    r"(-?\d+(?:\.\d+)?%|\$?\d+(?:\.\d+)?\s?(?:billion|million|bn|m|b)|\$\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)

_STRONG_SOURCE_TYPES: set[str] = {
    "sec_filing",
    "earnings_release",
    "company_presentation",
    "public:sec_edgar",
    "public:company_ir",
}
_MEDIUM_SOURCE_TYPES: set[str] = {
    "earnings_call_transcript",
    "reputable_financial_news",
    "company_ir_page",
    "public:earnings_transcript",
    "public:financial_news",
}
_WEAK_SOURCE_TYPES: set[str] = {
    "analyst_or_commentary",
    "public:analyst_or_commentary",
}

_FACT_MARKERS: tuple[str, ...] = (
    "reported",
    "increased",
    "decreased",
    "rose",
    "fell",
    "disclosed",
    "filed",
    "issued",
    "guidance",
    "10-q",
    "10-k",
    "8-k",
)
_INTERPRETATION_MARKERS: tuple[str, ...] = (
    "may",
    "might",
    "could",
    "appears",
    "seems",
    "likely",
    "unlikely",
    "concern",
    "worried",
    "investors may",
    "analysts",
    "sentiment",
    "valuation",
    "opinion",
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _fallback_category(text: str) -> str:
    if any(k in text for k in ("risk", "lawsuit", "regulat", "headwind", "decline", "drop")):
        return "risk_disclosure"
    if any(k in text for k in ("revenue", "profit", "margin", "guidance", "earnings", "cash flow")):
        return "financial_result"
    if any(k in text for k in ("acquisition", "partnership", "launch", "product", "roadmap")):
        return "strategy"
    if any(k in text for k in ("market", "compet", "industry", "sector", "demand")):
        return "market_reaction"
    return "general"


def _fact_vs_interpretation(text: str, has_numeric: bool, source_type: str) -> tuple[str, str]:
    is_interpretive = _contains_any(text, _INTERPRETATION_MARKERS)
    has_fact_marker = _contains_any(text, _FACT_MARKERS)
    is_official_source = source_type in _STRONG_SOURCE_TYPES

    if is_interpretive and not (has_numeric and is_official_source):
        return "interpretation", "Claim contains speculative or narrative language."
    if has_numeric or has_fact_marker or is_official_source:
        return "fact", "Claim is verifiable and tied to reported/official information."
    return "interpretation", "Claim is descriptive but not clearly verifiable."


def _evidence_strength(
    source_type: str,
    has_numeric: bool,
    fact_or_interpretation: str,
) -> tuple[str, str]:
    if source_type in _STRONG_SOURCE_TYPES and (has_numeric or fact_or_interpretation == "fact"):
        return "strong", "Official source with quantitative/verifiable reported claim."
    if source_type in _WEAK_SOURCE_TYPES:
        return "weak", "Lower-reliability commentary or sentiment-oriented source."
    if source_type in _MEDIUM_SOURCE_TYPES:
        return "medium", "Credible source but often includes interpretation/context."
    if has_numeric and fact_or_interpretation == "fact":
        return "medium", "Quantitative claim from non-official source."
    return "weak", "Insufficiently verifiable claim from lower-confidence context."


def _confidence(strength: str, fact_or_interpretation: str, has_numeric: bool) -> float:
    if strength == "strong":
        base = 0.93
    elif strength == "medium":
        base = 0.78
    else:
        base = 0.56
    if fact_or_interpretation == "fact":
        base += 0.03
    if has_numeric:
        base += 0.02
    return round(min(0.99, max(0.35, base)), 2)


def _normalized_strength(value: str) -> str:
    lower = value.strip().lower()
    return lower if lower in {"strong", "medium", "weak"} else "weak"


def _normalized_fact_or_interpretation(value: str) -> str:
    lower = value.strip().lower()
    return lower if lower in {"fact", "interpretation"} else "interpretation"


def _llm_classify_evidences(evidences: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    payload_evidences: list[dict[str, Any]] = []
    for idx, ev in enumerate(evidences):
        payload_evidences.append(
            {
                "idx": idx,
                "claim": str(ev.get("claim") or ev.get("text") or "").strip(),
                "category": str(ev.get("category") or "").strip(),
                "source_type": str(ev.get("source_type") or "").strip(),
                "period": str(ev.get("period") or "").strip(),
                "metric": str(ev.get("metric") or "").strip(),
                "value": str(ev.get("value") or "").strip(),
            }
        )

    result = invoke_prompt_json(
        prompt_filename="evidence_classifier.md",
        payload={"evidences": payload_evidences},
        output_schema_hint="""
{
  "classified_evidences": [
    {
      "idx": 0,
      "evidence_strength": "strong|medium|weak",
      "fact_or_interpretation": "fact|interpretation",
      "confidence": 0.0,
      "reason": "string"
    }
  ]
}
""".strip(),
    )

    raw_items = result.get("classified_evidences") if isinstance(result, dict) else None
    if not isinstance(raw_items, list):
        return {}

    out: dict[int, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if not isinstance(idx, int | float | str):
            continue
        try:
            i = int(idx)
        except Exception:
            continue
        if i < 0 or i >= len(evidences) or i in out:
            continue
        confidence_raw = item.get("confidence")
        if not isinstance(confidence_raw, int | float | str):
            confidence_raw = 0.65
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = 0.65
        out[i] = {
            "evidence_strength": _normalized_strength(str(item.get("evidence_strength") or "")),
            "fact_or_interpretation": _normalized_fact_or_interpretation(
                str(item.get("fact_or_interpretation") or "")
            ),
            "confidence": round(min(0.99, max(0.35, confidence)), 2),
            "reason": str(item.get("reason") or "").strip(),
        }
    return out


@observe(name="agents.graph.nodes.evidence_classifier.evidence_classifier_node")
def evidence_classifier_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Classify evidence items by:
    - evidence_strength: strong | medium | weak
    - fact_or_interpretation: fact | interpretation
    - confidence: float [0, 1]
    - reason: concise explanation

    Output:
    - classified_evidences: list[dict] evidence + classification fields
    """
    try:
        evidences = state.get("evidences")
        if not isinstance(evidences, list) or not evidences:
            return {"classified_evidences": [], "warning": state.get("warning"), "error": None}

        llm_warning: str | None = None
        llm_classifications: dict[int, dict[str, Any]] = {}
        try:
            llm_classifications = _llm_classify_evidences(
                [ev for ev in evidences if isinstance(ev, dict)]
            )
        except Exception as exc:
            llm_warning = f"evidence_classifier LLM fallback: {exc}"

        out: list[dict[str, Any]] = []
        for idx, ev in enumerate(evidences):
            if not isinstance(ev, dict):
                continue
            text = str(ev.get("claim") or ev.get("text") or "").strip()
            if not text:
                continue

            llm_item = llm_classifications.get(idx)
            if llm_item:
                evidence_strength = str(llm_item.get("evidence_strength") or "weak")
                fact_or_interpretation = str(
                    llm_item.get("fact_or_interpretation") or "interpretation"
                )
                confidence = float(llm_item.get("confidence") or 0.65)
                reason = str(llm_item.get("reason") or "").strip()
            else:
                lower_text = text.lower()
                source_type = str(ev.get("source_type") or "unknown").strip().lower()
                has_numeric = _NUMERIC_RE.search(text) is not None
                fact_or_interpretation, fact_reason = _fact_vs_interpretation(
                    text=lower_text,
                    has_numeric=has_numeric,
                    source_type=source_type,
                )
                evidence_strength, strength_reason = _evidence_strength(
                    source_type=source_type,
                    has_numeric=has_numeric,
                    fact_or_interpretation=fact_or_interpretation,
                )
                confidence = _confidence(
                    strength=evidence_strength,
                    fact_or_interpretation=fact_or_interpretation,
                    has_numeric=has_numeric,
                )
                reason = f"{strength_reason} {fact_reason}".strip()

            enriched = dict(ev)
            if not str(enriched.get("category") or "").strip():
                enriched["category"] = _fallback_category(text.lower())
            enriched["claim"] = str(enriched.get("claim") or text).strip()
            enriched["evidence_strength"] = evidence_strength
            enriched["fact_or_interpretation"] = fact_or_interpretation
            enriched["confidence"] = confidence
            enriched["reason"] = reason or "Classified by prompt-driven rubric."
            out.append(enriched)

        warning_parts = [str(state.get("warning") or "").strip()]
        if llm_warning:
            warning_parts.append(llm_warning)
        return {
            "classified_evidences": out,
            "warning": " | ".join(part for part in warning_parts if part) or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "classified_evidences": state.get("classified_evidences"),
            "warning": f"evidence_classifier fallback: {exc}",
            "error": None,
        }
