import os
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


def get_llm() -> BaseChatModel:
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini").strip()
    provider = _normalized_provider()  # openai | anthropic | ...
    env_key = _required_api_key_env(provider)
    if env_key and not os.getenv(env_key):
        raise OSError(f"{env_key} is not set in environment/.env")

    callbacks = _get_langfuse_callbacks()
    return init_chat_model(
        model=model_name,
        model_provider=provider,
        callbacks=callbacks,
    )
