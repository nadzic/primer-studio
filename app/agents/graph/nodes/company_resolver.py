from __future__ import annotations

import re
from collections.abc import Mapping

from app.observability.tracing import observe

_TICKER_RE = re.compile(r"\b[A-Z]{1,6}\b")

_MAG7: dict[str, dict[str, str]] = {
    "AAPL": {
        "company_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Information Technology",
        "industry": "Consumer Electronics",
    },
    "AMZN": {
        "company_name": "Amazon.com, Inc.",
        "exchange": "NASDAQ",
        "sector": "Consumer Discretionary",
        "industry": "Internet Retail and Cloud Infrastructure",
    },
    "GOOG": {
        "company_name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Internet Content and Digital Advertising",
    },
    "GOOGL": {
        "company_name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Internet Content and Digital Advertising",
    },
    "META": {
        "company_name": "Meta Platforms, Inc.",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "industry": "Social Platforms and Digital Advertising",
    },
    "MSFT": {
        "company_name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "sector": "Information Technology",
        "industry": "Software and Cloud Platforms",
    },
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "exchange": "NASDAQ",
        "sector": "Information Technology",
        "industry": "Semiconductors and Accelerated Computing",
    },
    "TSLA": {
        "company_name": "Tesla, Inc.",
        "exchange": "NASDAQ",
        "sector": "Consumer Discretionary",
        "industry": "Electric Vehicles and Energy Systems",
    },
}

_NAME_ALIASES: dict[str, str] = {
    "APPLE": "AAPL",
    "AMAZON": "AMZN",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
}


def _guess_company_from_query(query: str) -> str | None:
    q = (query or "").strip()
    if not q:
        return None

    # Heuristic: if user wrote something like "Research Apple" / "Tell me about OpenAI"
    cleaned = re.sub(
        r"(?i)\b(research|analyze|analyse|tell me about|about|company)\b", "", q
    ).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


@observe(name="agents.graph.nodes.company_resolver.company_resolver_node")
def company_resolver_node(state: Mapping[str, object]) -> dict[str, object | None]:
    """
    Normalize "who are we researching?" into:
    - company_name: best-effort string (may be same as symbol)
    - symbol: optional ticker if present

    This is intentionally heuristic and safe: it should never raise.
    """
    try:
        query = str(state.get("query") or state.get("input_query") or "").strip()
        symbol = str(state.get("symbol") or "").strip().upper()

        if not symbol and query:
            tickers = _TICKER_RE.findall(query)
            if tickers:
                symbol = tickers[-1].upper()

        company_name = str(state.get("company_name") or "").strip()
        if not company_name:
            company_name = _guess_company_from_query(query) or (symbol if symbol else "")

        company_name = company_name.strip()

        # Magnificent 7 only (for now): normalize from ticker or company-name alias.
        normalized_symbol = symbol
        if not normalized_symbol and company_name:
            normalized_symbol = _NAME_ALIASES.get(company_name.strip().upper(), "")

        normalized_symbol = normalized_symbol.strip().upper() if normalized_symbol else ""

        if normalized_symbol in _MAG7:
            meta = _MAG7[normalized_symbol]
            return {
                "company_name": meta["company_name"],
                "symbol": normalized_symbol,
                "sector": meta.get("sector"),
                "industry": meta.get("industry"),
                "warning": state.get("warning"),
                "error": None,
            }

        supported = ", ".join(sorted({k for k in _MAG7.keys() if k != "GOOG"}))
        warning_prefix = str(state.get("warning") or "").strip()
        warning = " | ".join(
            [
                w
                for w in [
                    warning_prefix,
                    "Non‑Mag7 company: coverage may be limited; using fallback retrieval.",
                    f"Mag7 has best coverage. Supported tickers: {supported}",
                ]
                if w
            ]
        )

        return {
            "company_name": company_name or None,
            "symbol": symbol or None,
            "sector": str(state.get("sector") or "").strip() or None,
            "industry": str(state.get("industry") or "").strip() or None,
            "warning": warning or None,
            "error": None,
        }
    except Exception as exc:
        return {
            "company_name": state.get("company_name"),
            "symbol": state.get("symbol"),
            "sector": state.get("sector"),
            "industry": state.get("industry"),
            "warning": f"company_resolver fallback: {exc}",
            "error": None,
        }
