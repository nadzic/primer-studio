#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "evals" / "datasets" / "signals_analyze_golden_v1.json"
DEFAULT_ENDPOINT = "/api/v1/research"
BRIEF_SECTIONS = (
    "what_changed",
    "what_matters_most_now",
    "bull_points",
    "bear_points",
    "what_to_watch_next",
)
NON_PUBLIC_TERMS = {"insider", "non-public", "nonpublic", "leaked", "material nonpublic"}
RECOMMENDATION_PATTERNS = (
    re.compile(r"\b(should|must|definitely|strongly)\s+(buy|sell|hold)\b", re.I),
    re.compile(r"\b(buy|sell|hold)\s+(this|now|today|immediately)\b", re.I),
    re.compile(r"\b(my\s+call|recommendation)\s+is\s+(buy|sell|hold)\b", re.I),
)


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    checks_passed: int
    checks_total: int
    failures: list[str]
    warning: str | None = None
    error: str | None = None

    def score(self) -> float:
        if self.checks_total == 0:
            return 0.0
        return self.checks_passed / self.checks_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run contract-style evals against /api/v1/research.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Endpoint path (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"Path to dataset JSON (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="HTTP timeout in seconds (default: 90)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Fail a case if API response includes warning.",
    )
    return parser.parse_args()


def load_dataset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Dataset must be a list of cases: {path}")
    return payload


def _iter_brief_points(brief: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for section in BRIEF_SECTIONS:
        value = brief.get(section)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    points.append(item)
    return points


def _collect_all_text(response_payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    brief = response_payload.get("brief")
    if isinstance(brief, dict):
        summary = brief.get("executive_summary")
        if isinstance(summary, str):
            chunks.append(summary)
        for point in _iter_brief_points(brief):
            text = point.get("text")
            if isinstance(text, str):
                chunks.append(text)
    warning = response_payload.get("warning")
    if isinstance(warning, str):
        chunks.append(warning)
    return "\n".join(chunks)


def _sources_look_public(response_payload: dict[str, Any]) -> bool:
    urls: list[str] = []

    for key in ("sources", "selected_evidence"):
        value = response_payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            for url_key in ("url", "source_url", "source_id", "source"):
                raw = item.get(url_key)
                if isinstance(raw, str) and raw.strip():
                    urls.append(raw.strip())

    brief = response_payload.get("brief")
    if isinstance(brief, dict):
        for point in _iter_brief_points(brief):
            raw = point.get("source_url")
            if isinstance(raw, str) and raw.strip():
                urls.append(raw.strip())

    if not urls:
        return True

    for raw in urls:
        lowered = raw.lower()
        if any(term in lowered for term in NON_PUBLIC_TERMS):
            return False
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc:
            return False
    return True


def _has_direct_buy_sell_call(text: str) -> bool:
    lowered = text.lower()
    if "not investment advice" in lowered:
        # Keep scanning anyway, but disclaimer alone should not mask violations.
        pass
    return any(pattern.search(text) is not None for pattern in RECOMMENDATION_PATTERNS)


def evaluate_case(
    case: dict[str, Any],
    response_payload: dict[str, Any],
    *,
    fail_on_warning: bool,
) -> CaseResult:
    checks_total = 0
    checks_passed = 0
    failures: list[str] = []

    case_id = str(case.get("id", "unknown"))
    expected_sections = case.get("required_sections", [])
    required_properties = case.get("required_properties", {})

    brief = response_payload.get("brief")
    if not isinstance(brief, dict):
        return CaseResult(
            case_id=case_id,
            passed=False,
            checks_passed=0,
            checks_total=1,
            failures=["missing_or_invalid_brief_object"],
            warning=response_payload.get("warning"),
            error=response_payload.get("error"),
        )

    checks_total += 1
    has_all_sections = True
    for section in expected_sections:
        if section not in brief or not isinstance(brief.get(section), list):
            has_all_sections = False
            failures.append(f"missing_or_invalid_section:{section}")
    if has_all_sections:
        checks_passed += 1

    all_points = _iter_brief_points(brief)

    if required_properties.get("separates_fact_vs_interpretation", False):
        checks_total += 1
        point_types = {
            str(point.get("type", "")).strip().lower()
            for point in all_points
            if isinstance(point.get("type"), str)
        }
        if "fact" in point_types and "interpretation" in point_types:
            checks_passed += 1
        else:
            failures.append("missing_fact_and_interpretation_separation")

    if required_properties.get("public_sources_only", False):
        checks_total += 1
        if _sources_look_public(response_payload):
            checks_passed += 1
        else:
            failures.append("non_public_or_invalid_source_detected")

    full_text = _collect_all_text(response_payload)
    if required_properties.get("no_direct_buy_sell_call", False):
        checks_total += 1
        if not _has_direct_buy_sell_call(full_text):
            checks_passed += 1
        else:
            failures.append("contains_direct_buy_sell_recommendation")

    checks_total += 1
    disclaimer = str(response_payload.get("disclaimer", "")).lower()
    if "not investment advice" in disclaimer:
        checks_passed += 1
    else:
        failures.append("missing_disclaimer")

    if fail_on_warning:
        checks_total += 1
        warning = response_payload.get("warning")
        if warning is None:
            checks_passed += 1
        else:
            failures.append("warning_present")

    passed = checks_passed == checks_total
    return CaseResult(
        case_id=case_id,
        passed=passed,
        checks_passed=checks_passed,
        checks_total=checks_total,
        failures=failures,
        warning=response_payload.get("warning"),
        error=response_payload.get("error"),
    )


def call_research_api(
    client: httpx.Client,
    *,
    base_url: str,
    endpoint: str,
    query: str,
) -> tuple[int, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    response = client.post(url, json={"query": query})
    payload: dict[str, Any]
    try:
        payload = response.json()
    except Exception:
        payload = {"_raw_text": response.text}
    return response.status_code, payload


def main() -> int:
    args = parse_args()
    cases = load_dataset(args.dataset)

    print(f"Dataset: {args.dataset}")
    print(f"Target: {args.base_url.rstrip('/')}/{args.endpoint.lstrip('/')}")
    print(f"Cases: {len(cases)}\n")

    results: list[CaseResult] = []
    with httpx.Client(timeout=args.timeout) as client:
        for case in cases:
            case_id = str(case.get("id", "unknown"))
            query = case.get("input", {}).get("query", "")
            if not isinstance(query, str) or not query.strip():
                results.append(
                    CaseResult(
                        case_id=case_id,
                        passed=False,
                        checks_passed=0,
                        checks_total=1,
                        failures=["invalid_or_missing_input_query"],
                    )
                )
                continue

            try:
                status_code, payload = call_research_api(
                    client,
                    base_url=args.base_url,
                    endpoint=args.endpoint,
                    query=query.strip(),
                )
            except Exception as exc:
                results.append(
                    CaseResult(
                        case_id=case_id,
                        passed=False,
                        checks_passed=0,
                        checks_total=1,
                        failures=[f"api_call_failed:{exc}"],
                    )
                )
                continue

            if status_code != 200:
                results.append(
                    CaseResult(
                        case_id=case_id,
                        passed=False,
                        checks_passed=0,
                        checks_total=1,
                        failures=[f"non_200_status:{status_code}"],
                        error=str(payload.get("detail") or payload),
                    )
                )
                continue

            results.append(
                evaluate_case(
                    case,
                    payload,
                    fail_on_warning=args.fail_on_warning,
                )
            )

    passed_count = sum(1 for item in results if item.passed)
    total_count = len(results)
    avg_score = (sum(item.score() for item in results) / total_count) if total_count else 0.0

    print("Per-case results:")
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"- {item.case_id}: {status} ({item.checks_passed}/{item.checks_total})")
        if item.failures:
            print(f"  failures: {', '.join(item.failures)}")
        if item.warning:
            print(f"  warning: {item.warning}")
        if item.error:
            print(f"  error: {item.error}")

    print("\nSummary:")
    print(f"- Passed: {passed_count}/{total_count}")
    print(f"- Average score: {avg_score:.2%}")

    report_payload = {
        "dataset": str(args.dataset),
        "target": f"{args.base_url.rstrip('/')}/{args.endpoint.lstrip('/')}",
        "summary": {
            "passed": passed_count,
            "total": total_count,
            "average_score": avg_score,
        },
        "results": [
            {
                "id": item.case_id,
                "passed": item.passed,
                "checks_passed": item.checks_passed,
                "checks_total": item.checks_total,
                "failures": item.failures,
                "warning": item.warning,
                "error": item.error,
            }
            for item in results
        ],
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report_payload, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\nReport written: {args.out}")

    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
