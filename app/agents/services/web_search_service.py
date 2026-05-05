from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

_ = load_dotenv()

WebSearchProvider = Literal["tavily"]

_CACHE: dict[str, tuple[float, list[WebSearchResult]]] = {}


@dataclass(frozen=True)
class WebSearchResult:
    rank: int
    url: str
    title: str | None
    snippet: str
    score: float | None = None
    provider: WebSearchProvider = "tavily"


def _normalized_provider() -> WebSearchProvider:
    raw = os.getenv("WEB_SEARCH_PROVIDER", "tavily").strip().lower()
    return "tavily" if raw != "tavily" else "tavily"


def _has_tavily_key() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def web_search_available() -> bool:
    provider = _normalized_provider()
    if provider == "tavily":
        return _has_tavily_key()
    return False


def search_public_web(
    query: str,
    *,
    max_results: int = 8,
    search_depth: Literal["basic", "advanced"] = "advanced",
    timeout_s: float = 25.0,
) -> list[WebSearchResult]:
    """
    Search the public web and return compact results.

    Intended as a lightweight "source discovery" step (URLs + snippets),
    not full web scraping.
    """
    q = query.strip()
    if not q:
        return []

    # Stabilize repeated runs within a server session:
    # - Deterministic mode: reuse the first observed result set for the same query params.
    # - Default mode: reuse results within a short TTL to reduce jitter.
    det = str(os.getenv("DETERMINISTIC_MODE", "0") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }
    ttl_s_raw = os.getenv("WEB_SEARCH_CACHE_TTL_S", "180").strip()
    try:
        ttl_s = float(ttl_s_raw)
    except Exception:
        ttl_s = 180.0

    cache_key = f"{q.lower()}||{max_results}||{search_depth}"
    cached = _CACHE.get(cache_key)
    now = time.time()
    if cached is not None:
        ts, results = cached
        if det or (ttl_s > 0 and (now - ts) <= ttl_s):
            return list(results)

    provider = _normalized_provider()
    if provider == "tavily":
        results = _tavily_search(
            q, max_results=max_results, search_depth=search_depth, timeout_s=timeout_s
        )
        _CACHE[cache_key] = (now, list(results))
        return results

    return []


def _tavily_search(
    query: str,
    *,
    max_results: int,
    search_depth: Literal["basic", "advanced"],
    timeout_s: float,
) -> list[WebSearchResult]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": max(1, min(int(max_results), 10)),
        "search_depth": search_depth,
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post("https://api.tavily.com/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results")
    if not isinstance(results, list):
        return []

    out: list[WebSearchResult] = []
    for idx, raw in enumerate(results, start=1):
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        title = str(raw.get("title") or "").strip() or None
        snippet = str(raw.get("content") or raw.get("snippet") or "").strip()
        if not snippet:
            continue
        score = raw.get("score")
        try:
            score_f = float(score) if score is not None else None
        except Exception:
            score_f = None

        out.append(
            WebSearchResult(
                rank=idx,
                url=url,
                title=title,
                snippet=snippet[:1200],
                score=score_f,
                provider="tavily",
            )
        )

    return out
