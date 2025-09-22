"""Conference helpers: outcome calculation and press builders."""

from __future__ import annotations

from typing import Tuple

from ..models import PressRelease
from ..press import GossipContext, academic_gossip
from ..models import ExpeditionOutcome


def compute_conference_outcome(
    base_roll: int, *, supporters: int, opposition: int
) -> Tuple[ExpeditionOutcome, int, int, int]:
    """Calculate conference outcome from a base roll and support/opposition counts.

    Returns (outcome, final_roll, support_modifier, opposition_modifier).
    """

    support_modifier = supporters * 5
    opposition_modifier = opposition * 5
    final_roll = base_roll + support_modifier - opposition_modifier
    if final_roll >= 60:
        outcome = ExpeditionOutcome.SUCCESS
    elif final_roll >= 40:
        outcome = ExpeditionOutcome.PARTIAL
    else:
        outcome = ExpeditionOutcome.FAILURE
    return outcome, final_roll, support_modifier, opposition_modifier


def build_conference_announcement_press(
    *, player_display: str, code: str, theory_text: str
) -> PressRelease:
    quote = f"Conference {code} announced to debate: {theory_text}"
    return academic_gossip(
        GossipContext(
            scholar=player_display,
            quote=quote,
            trigger=f"Conference on theory",
        )
    )


def build_conference_resolution_press(
    *, code: str, outcome: ExpeditionOutcome, reputation_delta: int
) -> PressRelease:
    outcome_text = {
        ExpeditionOutcome.SUCCESS: "The conference concluded with resounding support for the theory",
        ExpeditionOutcome.PARTIAL: "The conference ended with mixed opinions",
        ExpeditionOutcome.FAILURE: "The conference thoroughly rejected the theory",
    }[outcome]
    quote = (
        f"Conference {code} result: {outcome_text}. Reputation change: {reputation_delta:+d}"
    )
    return academic_gossip(
        GossipContext(
            scholar="The Academy",
            quote=quote,
            trigger=f"Conference {code} resolution",
        )
    )


__all__ = [
    "compute_conference_outcome",
    "build_conference_announcement_press",
    "build_conference_resolution_press",
]

