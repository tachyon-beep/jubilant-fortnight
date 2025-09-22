"""Recruitment calculations and relationship bonus helpers."""

from __future__ import annotations

from typing import Dict

from ..models import Player, Scholar


def compute_recruitment_chance(
    *, player: Player, faction: str, base_chance: float
) -> Dict[str, float | int | bool]:
    """Calculate recruitment odds modifiers for the given faction."""

    raw_influence = player.influence.get(faction, 0)
    influence_bonus = max(0, raw_influence) * 0.05
    cooldown_remaining = int(player.cooldowns.get("recruitment", 0) or 0)
    cooldown_penalty = 0.5 if cooldown_remaining else 1.0
    chance = max(0.05, min(0.95, base_chance * cooldown_penalty + influence_bonus))
    return {
        "chance": chance,
        "influence_bonus": influence_bonus,
        "cooldown_penalty": cooldown_penalty,
        "cooldown_active": bool(cooldown_remaining),
        "cooldown_remaining": cooldown_remaining,
        "influence": raw_influence,
    }


def relationship_bonus(
    *, scholar: Scholar, player_id: str, active_for_player: bool
) -> Dict[str, float | int | bool]:
    """Compute relationship-based recruiting modifier components."""

    feeling = scholar.memory.feelings.get(player_id, 0.0)
    base_bonus = max(-0.2, min(0.2, feeling * 0.02))

    mentorship_bonus = 0.0
    if active_for_player:
        mentorship_bonus += 0.05
    else:
        history = scholar.contract.get("mentorship_history")
        if isinstance(history, list):
            entries = [entry for entry in history if entry.get("mentor_id") == player_id]
            if entries:
                last_event = entries[-1].get("event")
                if last_event == "completion":
                    mentorship_bonus += 0.04
                else:
                    mentorship_bonus += 0.02

    sidecast_bonus = 0.0
    sidecasts = scholar.contract.get("sidecast_history")
    if isinstance(sidecasts, list):
        if any(entry.get("sponsor_id") == player_id for entry in sidecasts):
            sidecast_bonus += 0.02

    total = base_bonus + mentorship_bonus + sidecast_bonus
    total = max(-0.25, min(0.25, total))

    return {
        "total": total,
        "feeling": feeling,
        "base_bonus": base_bonus,
        "mentorship_bonus": mentorship_bonus,
        "sidecast_bonus": sidecast_bonus,
        "active_mentorship": active_for_player,
    }


__all__ = ["compute_recruitment_chance", "relationship_bonus"]

