"""Narrative service helpers.

Wrappers provide a stable import surface for narrative generation and related
concerns while we migrate logic out of the legacy service module.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List

from ..llm_client import (
    LLMGenerationError,
    LLMNotEnabledError,
    enhance_press_release_sync as _llm_enhance_press_release_sync,
)
from ..multi_press import MultiPressGenerator

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


# Multipress orchestration wrappers -------------------------------------------

def determine_depth(
    multi: MultiPressGenerator,
    *,
    event_type: str,
    reputation_change: Optional[int] = None,
    confidence_level: Optional[str] = None,
    is_first_time: Optional[bool] = None,
) -> Any:
    return multi.determine_depth(
        event_type=event_type,
        reputation_change=reputation_change,
        confidence_level=confidence_level,
        is_first_time=is_first_time,
    )


def generate_expedition_layers(
    multi: MultiPressGenerator,
    expedition_ctx: Any,
    outcome_ctx: Any,
    scholars: List[Any],
    depth: Any,
    *,
    prep_depth: str,
    preparation_summary: Dict[str, Any],
    team_names: List[str],
):
    return multi.generate_expedition_layers(
        expedition_ctx,
        outcome_ctx,
        scholars,
        depth,
        prep_depth=prep_depth,
        preparation_summary=preparation_summary,
        team_names=team_names,
    )


def generate_defection_layers(
    multi: MultiPressGenerator,
    defection_ctx: Any,
    scholar: Any,
    former_employer: str,
    scholars: List[Any],
    depth: Any,
):
    return multi.generate_defection_layers(
        defection_ctx, scholar, former_employer, scholars, depth
    )


def generate_symposium_layers(
    multi: MultiPressGenerator,
    *,
    topic: str,
    description: str,
    phase: str,
    scholars: List[Any],
):
    return multi.generate_symposium_layers(
        topic, description, phase=phase, scholars=scholars
    )


def generate_sidecast_layers(
    multi: MultiPressGenerator,
    *,
    arc_key: str,
    phase: str,
    scholar: Any,
    sponsor: str,
    expedition_type: Optional[str],
    expedition_code: Optional[str],
):
    return multi.generate_sidecast_layers(
        arc_key=arc_key,
        phase=phase,
        scholar=scholar,
        sponsor=sponsor,
        expedition_type=expedition_type,
        expedition_code=expedition_code,
    )

