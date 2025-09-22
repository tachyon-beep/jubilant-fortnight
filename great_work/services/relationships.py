"""Relationship aggregation helpers."""

from __future__ import annotations

from typing import Dict, Iterable

from ..models import Scholar


def faction_sentiments(scholars: Iterable[Scholar], *, player_id: str) -> Dict[str, Dict[str, float]]:
    """Aggregate average feelings per faction for a player's relations."""

    aggregates: Dict[str, Dict[str, float]] = {}
    for scholar in scholars:
        feeling = scholar.memory.feelings.get(player_id)
        if feeling is None:
            continue
        faction = (scholar.contract.get("faction") or "unaligned").lower()
        entry = aggregates.setdefault(faction, {"total": 0.0, "count": 0})
        entry["total"] += feeling
        entry["count"] += 1

    sentiments: Dict[str, Dict[str, float]] = {}
    for faction, payload in aggregates.items():
        count = payload["count"] or 1
        average = payload["total"] / count
        sentiments[faction] = {
            "average": average,
            "count": payload["count"],
        }
    return sentiments


__all__ = ["faction_sentiments"]

