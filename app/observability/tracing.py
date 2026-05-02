from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, TypeVar, overload

from dotenv import load_dotenv

_langfuse_available = False

try:
    from langfuse import observe as _langfuse_observe

    _langfuse_available = True
except Exception:
    _langfuse_observe = None

_ = load_dotenv()

F = TypeVar("F", bound=Callable[..., Any])


@overload
def observe(func: F, /) -> F: ...


@overload
def observe(*, name: str | None = None, **kwargs: Any) -> Callable[[F], F]: ...


def observe(func: F | None = None, /, **kwargs: Any) -> F | Callable[[F], F]:
    """
    Langfuse observe decorator with safe no-op fallback when dependency is unavailable.
    Supports both `@observe` and `@observe(name="...")` forms.
    """
    if _langfuse_available and _langfuse_observe is not None:
        if func is not None and callable(func):
            return _langfuse_observe(func)
        return _langfuse_observe(**kwargs)

    if func is not None and callable(func):
        return func

    def _decorator(inner: F) -> F:
        return inner

    return _decorator


def tracing_enabled() -> bool:
    return bool(
        _langfuse_available
        and os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
    )


__all__ = ["observe", "tracing_enabled"]
