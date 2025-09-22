"""Defection probability and offer acceptance helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, Tuple

from ..models import Scholar


def adjusted_defection_probability(
    scholar: Scholar,
    *,
    offer_quality: float,
    mistreatment: float,
    alignment: float,
    plateau: float,
    relationship_effect: float,
) -> float:
    """Combine base defection probability with relationship effect and clamp."""

    from ..scholars import defection_probability  # local import to avoid cycles

    base = defection_probability(scholar, offer_quality, mistreatment, alignment, plateau)
    return _clamp_probability(base + relationship_effect)


def choose_outcome(probability: float, *, random_uniform: Callable[[float, float], float]) -> Tuple[float, str]:
    """Pick outcome given a probability and a random source.

    Returns (roll, outcome) where outcome is "defected" or "refused".
    """

    roll = random_uniform(0.0, 1.0)
    return roll, ("defected" if roll < probability else "refused")


def offer_acceptance_probability(offer, scholar: Scholar, *, now: datetime | None = None) -> float:
    """Compute acceptance probability for a single offer based on feelings, terms, and history."""

    now = now or datetime.now(timezone.utc)
    total_influence = sum(offer.influence_offered.values())
    offer_quality = min(10.0, total_influence / 10.0)

    rival_feeling = scholar.memory.feelings.get(offer.rival_id, 0.0)
    patron_feeling = scholar.memory.feelings.get(offer.patron_id, 0.0)

    # Mistreatment factor (negative feelings toward current patron)
    mistreatment = max(0.0, -patron_feeling) / 5.0

    # Alignment factor (positive feelings toward rival)
    alignment = max(0.0, rival_feeling) / 5.0

    # Check for plateau (no recent discoveries)
    recent_discoveries = [
        fact
        for fact in scholar.memory.facts
        if getattr(fact, "kind", "") == "discovery"
        and (now - getattr(fact, "when", now)).days < 90
    ]
    plateau = 0.0 if recent_discoveries else 0.2

    from ..scholars import defection_probability

    probability = defection_probability(
        scholar, offer_quality, mistreatment, alignment, plateau
    )

    # Adjust for contract terms
    terms = getattr(offer, "terms", {}) or {}
    if "exclusive_research" in terms:
        probability += 0.1
    if "guaranteed_funding" in terms:
        probability += 0.15
    if "leadership_role" in terms:
        probability += 0.2

    # Adjust for offer type (counters have slight advantage to current patron)
    if getattr(offer, "offer_type", "initial") == "counter":
        probability -= 0.1

    return _clamp_probability(probability)


def _clamp_probability(value: float) -> float:
    return max(0.05, min(0.95, value))


__all__ = [
    "adjusted_defection_probability",
    "choose_outcome",
    "offer_acceptance_probability",
]

