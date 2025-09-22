"""Expedition press helpers and context builders."""

from __future__ import annotations

from typing import Dict, List

from ..models import PressRelease
from ..press import (
    ExpeditionContext,
    OutcomeContext,
    research_manifesto,
    discovery_report,
    retraction_notice,
)
from ..models import ExpeditionPreparation


def make_manifesto(
    *,
    code: str,
    player_id: str,
    expedition_type: str,
    objective: str,
    team: List[str],
    funding: List[str],
    prep_depth: str,
    preparation_strengths: str,
    preparation_frictions: str,
) -> PressRelease:
    """Create a research manifesto press for a queued expedition."""

    ctx = ExpeditionContext(
        code=code,
        player=player_id,
        expedition_type=expedition_type,
        objective=objective,
        team=team,
        funding=funding,
        prep_depth=prep_depth,
        preparation_strengths=preparation_strengths,
        preparation_frictions=preparation_frictions,
    )
    return research_manifesto(ctx)


def make_result_release(*, ctx: OutcomeContext) -> PressRelease:
    """Create a result press (discovery or retraction) for a resolved expedition.

    Expects a fully-formed OutcomeContext created by the caller.
    """
    # Choose release type based on outcome
    result = getattr(ctx, "result", None)
    if getattr(result, "outcome", None) and result.outcome.value == "failure":
        return retraction_notice(ctx)
    if getattr(result, "outcome", None) and getattr(result.outcome, "name", "") == "FAILURE":
        return retraction_notice(ctx)
    return discovery_report(ctx)


__all__ = ["make_manifesto", "make_result_release"]


def summarize_preparation(preparation: ExpeditionPreparation):
    """Summarize preparation bonuses/frictions into structured and text lists."""

    mapping = (
        ("think_tank_bonus", "Think tank modelling"),
        ("expertise_bonus", "Field expertise"),
        ("site_friction", "Site friction"),
        ("political_friction", "Political currents"),
    )
    strengths = []
    frictions = []
    strengths_text = []
    frictions_text = []

    for attr, label in mapping:
        value = getattr(preparation, attr, 0)
        if value == 0:
            continue
        formatted = f"{label} {value:+d}"
        entry = {"label": label, "value": value}
        if attr in {"think_tank_bonus", "expertise_bonus"}:
            if value > 0:
                strengths.append(entry)
                strengths_text.append(formatted)
            else:
                frictions.append(entry)
                frictions_text.append(formatted)
        else:
            if value < 0:
                frictions.append(entry)
                frictions_text.append(formatted)
            else:
                strengths.append(entry)
                strengths_text.append(formatted)

    return {
        "strengths": strengths,
        "frictions": frictions,
        "strengths_text": strengths_text,
        "frictions_text": frictions_text,
    }
