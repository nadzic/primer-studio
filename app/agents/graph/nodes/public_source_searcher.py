from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from app.agents.services.web_search_service import search_public_web, web_search_available
from app.observability.tracing import observe

_DENIED_TERMS: tuple[str, ...] = (
    "bloomberg terminal",
    "factset",
    "refinitiv",
    "private research",
    "internal company",
    "paid dataset",
    "private dataset",
)

_DENIED_DOMAINS: tuple[str, ...] = (
    "myterminal.bloomberg.com",
    "workspace.refinitiv.com",
    "factset.com",
)

_SEC_DOMAINS: tuple[str, ...] = ("sec.gov",)
_IR_DOMAIN_MARKERS: tuple[str, ...] = (
    "investor",
    "investors",
    "ir.",
)
_TRANSCRIPT_MARKERS: tuple[str, ...] = (
    "transcript",
    "earnings call",
    "prepared remarks",
)
_REPUTABLE_FINANCIAL_NEWS_DOMAINS: tuple[str, ...] = (
    "reuters.com",
    "wsj.com",
    "ft.com",
    "finance.yahoo.com",
    "marketwatch.com",
    "cnbc.com",
    "bloomberg.com",
)


def _extract_host(url: str) -> str:
    host = urlparse(url).netloc.lower().strip()
    return host[4:] if host.startswith("www.") else host


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_allowed_public_source(url: str, title: str | None, snippet: str) -> bool:
    host = _extract_host(url)
    combined = f"{(title or '').lower()} {snippet.lower()} {host}"
    if _contains_any(host, _DENIED_DOMAINS):
        return False
    if _contains_any(combined, _DENIED_TERMS):
        return False
    return True


def _classify_source_type(url: str, title: str | None, snippet: str) -> str:
    host = _extract_host(url)
    lower_title = (title or "").lower()
    lower_snippet = snippet.lower()
    combined = f"{lower_title} {lower_snippet} {host}"

    if host.endswith(_SEC_DOMAINS):
        return "public:sec_edgar"
    if _contains_any(host, _IR_DOMAIN_MARKERS) or _contains_any(combined, ("investor relations",)):
        return "public:company_ir"
    if _contains_any(combined, _TRANSCRIPT_MARKERS):
        return "public:earnings_transcript"
    if _contains_any(host, _REPUTABLE_FINANCIAL_NEWS_DOMAINS):
        return "public:financial_news"
    return "public:analyst_or_commentary"


def _iter_query_inputs(state: Mapping[str, object]) -> list[tuple[str, str]]:
    planned = state.get("search_plan")
    out: list[tuple[str, str]] = []
    if isinstance(planned, list):
        for item in planned:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query") or "").strip()
            purpose = str(item.get("purpose") or "").strip() or "planned_search"
            if query:
                out.append((query, purpose))
    if out:
        return out

    search_queries = state.get("search_queries")
    if isinstance(search_queries, list) and search_queries:
        for item in search_queries:
            if isinstance(item, dict):
                query = str(item.get("query") or "").strip()
                purpose = str(item.get("purpose") or "").strip() or "planned_search"
            else:
                query = str(item).strip()
                purpose = "planned_search"
            if query:
                out.append((query, purpose))
        if out:
            return out

    query = str(state.get("query") or state.get("input_query") or "").strip()
    return [(query, "fallback_user_query")] if query else []


@observe(name="agents.graph.nodes.public_source_searcher.public_source_searcher_node")
def public_source_searcher_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Fetch candidate public sources via Tavily and apply public-source policy.

    Output:
    - sources: list[dict] raw chunk-like objects (rank, text, source_id/url, score, ...)
    """
    try:
        query_inputs = _iter_query_inputs(state)[:5]
        symbol = str(state.get("symbol") or "").strip().upper() or None

        all_chunks: list[dict[str, Any]] = []
        warnings: list[str] = []
        filtered_out_count = 0
        if not web_search_available():
            warnings.append("Public web search is unavailable (missing TAVILY_API_KEY).")
            return {
                "sources": [],
                "warning": " | ".join(
                    filter(None, [str(state.get("warning") or "").strip()] + warnings)
                )
                or None,
                "error": None,
            }

        for q, purpose in query_inputs:
            try:
                results = search_public_web(q, max_results=8, search_depth="advanced")
                for r in results:
                    if not _is_allowed_public_source(r.url, r.title, r.snippet):
                        filtered_out_count += 1
                        continue
                    all_chunks.append(
                        {
                            "rank": r.rank,
                            "score": r.score,
                            "text": r.snippet,
                            "source_id": r.url,
                            "source_type": _classify_source_type(r.url, r.title, r.snippet),
                            "symbol": symbol,
                            "url": r.url,
                            "title": r.title,
                            "query_purpose": purpose,
                        }
                    )
            except Exception as exc:
                warnings.append(f"web search exception: {q} ({exc})")

        if filtered_out_count > 0:
            warnings.append(f"Filtered out {filtered_out_count} not-allowed sources.")

        return {
            "sources": all_chunks,
            "warning": " | ".join(
                filter(None, [str(state.get("warning") or "").strip()] + warnings)
            )
            or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "sources": state.get("sources"),
            "warning": f"public_source_searcher fallback: {exc}",
            "error": None,
        }
