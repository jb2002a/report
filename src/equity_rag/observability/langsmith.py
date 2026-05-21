from __future__ import annotations

import os
from typing import Any

from equity_rag.config import Settings


def configure_langsmith(settings: Settings) -> None:
    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


def trace_metadata(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


def traceable(name: str | None = None):
    try:
        from langsmith import traceable as ls_traceable

        return ls_traceable(name=name) if name else ls_traceable()
    except ImportError:
        def decorator(func):
            return func

        return decorator
