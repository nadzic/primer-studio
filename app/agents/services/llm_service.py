import contextvars
import os
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
except Exception:
    LangfuseCallbackHandler = None

_ = load_dotenv()
_langfuse_callback_handler: Any | None = None
_PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_request_provider: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_llm_provider",
    default=None,
)
_request_model_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_llm_model_name",
    default=None,
)
_request_usage: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "request_llm_usage",
    default=None,
)


@contextmanager
def llm_request_overrides(*, provider: str | None = None, model_name: str | None = None):
    token_provider = _request_provider.set(provider.strip().lower() if provider else None)
    token_model = _request_model_name.set(model_name.strip() if model_name else None)
    try:
        yield
    finally:
        _request_provider.reset(token_provider)
        _request_model_name.reset(token_model)


def _tracing_enabled() -> bool:
    return bool(
        LangfuseCallbackHandler is not None
        and os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
    )


def _get_langfuse_callbacks() -> list[Any]:
    global _langfuse_callback_handler
    if not _tracing_enabled():
        return []
    if LangfuseCallbackHandler is None:
        return []

    if _langfuse_callback_handler is None:
        _langfuse_callback_handler = LangfuseCallbackHandler()
    return [_langfuse_callback_handler]


def _normalized_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def _required_api_key_env(provider: str) -> str | None:
    return _PROVIDER_KEY_MAP.get(provider)


def _env_flag(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default)
    return str(raw or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _llm_temperature() -> float | None:
    # Deterministic mode: prioritize repeatability over creativity.
    if _env_flag("DETERMINISTIC_MODE", "0"):
        return 0.0
    raw = os.getenv("LLM_TEMPERATURE", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except Exception:
        return None


@contextmanager
def llm_usage_tracker():
    """
    Track prompt/completion/total token usage for the current request.
    """
    token = _request_usage.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    try:
        yield
    finally:
        _request_usage.reset(token)


def add_llm_usage(usage: dict[str, Any] | None) -> None:
    """
    Best-effort accumulation of token usage from model responses.
    Accepts shapes like:
    - {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    - {"input_tokens": int, "output_tokens": int, "total_tokens": int} (Anthropic-style)
    """
    acc = _request_usage.get()
    if acc is None or not usage:
        return

    def _as_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    prompt = _as_int(usage.get("prompt_tokens"))
    completion = _as_int(usage.get("completion_tokens"))
    total = _as_int(usage.get("total_tokens"))

    # Provider variants
    if prompt == 0:
        prompt = _as_int(usage.get("input_tokens"))
    if completion == 0:
        completion = _as_int(usage.get("output_tokens"))
    if total == 0 and (prompt or completion):
        total = prompt + completion

    acc["prompt_tokens"] += max(0, prompt)
    acc["completion_tokens"] += max(0, completion)
    acc["total_tokens"] += max(0, total)


def get_llm_usage() -> dict[str, int] | None:
    acc = _request_usage.get()
    return dict(acc) if isinstance(acc, dict) else None


def get_llm() -> BaseChatModel:
    request_model = _request_model_name.get()
    request_provider = _request_provider.get()
    model_name = (request_model or os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")).strip()
    provider = (request_provider or _normalized_provider()).strip().lower()
    env_key = _required_api_key_env(provider)
    if env_key and not os.getenv(env_key):
        raise OSError(f"{env_key} is not set in environment/.env")

    callbacks = _get_langfuse_callbacks()
    temperature = _llm_temperature()
    init_kwargs: dict[str, Any] = {
        "model": model_name,
        "model_provider": provider,
        "callbacks": callbacks,
    }
    if temperature is not None:
        init_kwargs["temperature"] = temperature

    return init_chat_model(
        **init_kwargs,
    )
