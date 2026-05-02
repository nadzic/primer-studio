from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol, cast

# Allow running both:
# - python -m app.agents.main
# - python app/agents/main.py
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

import json
from typing import Any

from app.agents.graph.schemas import RiskLimits, SignalInput
from app.agents.graph.state import HedgeFundState
from pydantic import BaseModel

from app.agents.graph.workflow import build_graph


def _to_jsonable(value: Any) -> Any:
    """Recursively convert Pydantic/models/containers to JSON-serializable objects."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    return value


def _print_json(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(_to_jsonable(payload), indent=2, ensure_ascii=False))


class _GraphRunner(Protocol):
    def invoke(self, input: HedgeFundState, /) -> HedgeFundState: ...


def _prompt_input() -> SignalInput:
    query = input("Query: ").strip()
    symbol = input("Symbol (e.g. AAPL): ").strip().upper()
    horizon = input("Horizon [intraday/swing/position]: ").strip().lower() or "swing"
    return SignalInput(query=query, symbol=symbol, horizon=horizon)


def _initial_state(user_input: SignalInput) -> HedgeFundState:
    return {
        "input": user_input,
        "risk_limits": RiskLimits(min_confidence=0.60, max_position_size=0.10),
        "analyst_tasks": [],
        "analyst_outputs": [],
        "suggestion": None,
        "warning": None,
        "error": None,
        "rag_context": None,
        "rag_citations": [],
        "is_input_valid": False,
        "missing_fields": [],
        "clarification_question": None,
    }


def main() -> None:
    graph = cast(_GraphRunner, cast(object, build_graph()))
    # first input
    current_input = SignalInput(
        query="Should I buy?",
        symbol="AAPL",
        horizon="swing",
    )
    while True:
        state = _initial_state(current_input)
        # optional stream debug
        for idx, chunk in enumerate(cast(Any, graph).stream(state, stream_mode="updates"), start=1):
            _print_json(f"STREAM UPDATE #{idx}", chunk)
        result: HedgeFundState = graph.invoke(state)
        _print_json("FINAL STATE", result)
        error = result.get("error")
        warning = result.get("warning")
        suggestion = result.get("suggestion")
        if error == "input_validation_failed":
            print("\nInput is not sufficient for analysis.")
            print(
                "Clarification: Need additional clarification on the input. "
                "Please provide the following information: "
                "input inquiry should be at least 15 characters."
            )
            print("Please enter the information again:\n")
            current_input = _prompt_input()
            continue
        print("\n=== AI Hedge Fund MVP ===")
        print("warning:", warning)
        print("error:", error)
        if suggestion is None:
            print("suggestion: None")
        else:
            _print_json("FINAL SUGGESTION", suggestion)
        break


if __name__ == "__main__":
    main()
