"""Narrative service helpers.

These wrappers provide a stable import surface for narrative generation and
related concerns while we migrate logic out of the legacy service module.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..llm_client import (
    LLMGenerationError,
    LLMNotEnabledError,
    enhance_press_release_sync as _llm_enhance_press_release_sync,
)

__all__ = [
    "LLMGenerationError",
    "LLMNotEnabledError",
    "enhance_press_release_sync",
]


def enhance_press_release_sync(
    press_type: str,
    base_body: str,
    context: Optional[Dict[str, Any]] = None,
    persona_name: Optional[str] = None,
    persona_traits: Optional[Dict[str, Any]] = None,
) -> str:
    """Delegate to the LLM client while keeping a services import path.

    Tests monkeypatch `great_work.service.enhance_press_release_sync`; that path
    remains valid because `great_work.service` re-exports this symbol.
    """

    return _llm_enhance_press_release_sync(
        press_type,
        base_body,
        context or {},
        persona_name,
        persona_traits or {},
    )

