"""Sideways effect press builders."""

from __future__ import annotations

from typing import Optional

from ..models import PressRelease


def build_faction_shift_press(
    *, player_name: str, faction: str, amount: int, old: int, new: int, description: str
) -> PressRelease:
    return PressRelease(
        type="faction_shift",
        headline=f"Expedition Discovery Shifts {faction} Relations",
        body=(
            f"{description}. {player_name}'s {faction} influence changes by {amount} "
            f"(from {old} to {new})."
        ),
        metadata={"player": player_name, "faction": faction, "change": amount},
    )


def build_spawn_theory_press(
    *, player_name: str, theory_text: str, confidence_value: str, description: str
) -> PressRelease:
    return PressRelease(
        type="discovery_theory",
        headline="Discovery Spawns New Theory",
        body=(
            f"{description}. {player_name} proposes: '{theory_text}' with {confidence_value} confidence."
        ),
        metadata={"player": player_name, "theory": theory_text},
    )


def build_scholar_grudge_press(
    *, target_name: str, player_name: str, description: str
) -> PressRelease:
    return PressRelease(
        type="scholar_grudge",
        headline=f"{target_name} Objects to Expedition Approach",
        body=(
            f"{description}. {target_name} expresses concerns about {player_name}'s expedition methods."
        ),
        metadata={"scholar": target_name, "player": player_name},
    )


def build_conference_scheduled_press(*, player_name: str, description: str) -> PressRelease:
    return PressRelease(
        type="conference_scheduled",
        headline="Emergency Colloquium Scheduled",
        body=f"{description}. Conference scheduled to discuss expedition findings.",
        metadata={"player": player_name},
    )


def build_reputation_shift_press(
    *, player_name: str, amount: int, old: int, new: int, description: str
) -> PressRelease:
    return PressRelease(
        type="reputation_shift",
        headline="Discovery Affects Academic Standing",
        body=(
            f"{description}. {player_name}'s reputation changes by {amount} "
            f"(from {old} to {new})."
        ),
        metadata={"player": player_name, "change": amount},
    )


def build_opportunity_press(
    *, player_name: str, opportunity_type: str, expires_days: int, description: str
) -> PressRelease:
    return PressRelease(
        type="opportunity_unlocked",
        headline="New Opportunity Emerges",
        body=(
            f"{description}. Opportunity expires in {expires_days} days."
        ),
        metadata={"player": player_name, "opportunity": opportunity_type},
    )


__all__ = [
    "build_faction_shift_press",
    "build_spawn_theory_press",
    "build_scholar_grudge_press",
    "build_conference_scheduled_press",
    "build_reputation_shift_press",
    "build_opportunity_press",
]

