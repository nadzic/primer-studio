from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents.services.llm_service import get_llm

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "graph" / "prompts"


@lru_cache(maxsize=32)
def load_graph_prompt(prompt_filename: str) -> str:
    path = _PROMPTS_DIR / prompt_filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content)


def _extract_json_payload(text: str) -> Any:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()

    try:
        return json.loads(candidate)
    except Exception:
        pass

    first_obj = candidate.find("{")
    first_arr = candidate.find("[")
    starts = [idx for idx in [first_obj, first_arr] if idx >= 0]
    if not starts:
        raise ValueError("No JSON object or array found in model output.")
    start = min(starts)
    obj_end = candidate.rfind("}")
    arr_end = candidate.rfind("]")
    end = max(obj_end, arr_end)
    if end < start:
        raise ValueError("Malformed JSON payload in model output.")
    return json.loads(candidate[start : end + 1])


def invoke_prompt_json(
    *,
    prompt_filename: str,
    payload: dict[str, Any],
    output_schema_hint: str,
) -> Any:
    llm = get_llm()
    system_prompt = load_graph_prompt(prompt_filename)
    user_prompt = (
        "Input JSON:\n"
        f"{json.dumps(payload, ensure_ascii=True)}\n\n"
        "Return strictly valid JSON (no markdown). "
        "Do not include explanations outside the JSON payload.\n"
        f"Expected output shape:\n{output_schema_hint}"
    )

    response = llm.invoke([("system", system_prompt), ("human", user_prompt)])
    text = _message_content_to_text(getattr(response, "content", response))
    return _extract_json_payload(text)
