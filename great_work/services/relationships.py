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

from typing import Any, Callable, List


def relationship_summary(
    *,
    scholars: Iterable[Scholar],
    player_id: str,
    get_active_mentorship: Callable[[str], Any],
    limit: int = 5,
) -> List[Dict[str, object]]:
    """Summarize per-scholar relationship details for a player."""

    entries: List[Dict[str, object]] = []
    for scholar in scholars:
        feeling = scholar.memory.feelings.get(player_id)
        mentorship_history = scholar.contract.get("mentorship_history")
        mentorship_entries = []
        if isinstance(mentorship_history, list):
            mentorship_entries = [
                entry for entry in mentorship_history if entry.get("mentor_id") == player_id
            ]
        sidecast_history = scholar.contract.get("sidecast_history")
        sidecast_entries = []
        if isinstance(sidecast_history, list):
            sidecast_entries = [
                entry for entry in sidecast_history if entry.get("sponsor_id") == player_id
            ]
        if feeling is None and not mentorship_entries and not sidecast_entries:
            continue
        active = get_active_mentorship(scholar.id)
        active_for_player = bool(active and active[1] == player_id)
        last_mentorship_event = None
        last_mentorship_at = None
        if mentorship_entries:
            last_entry = mentorship_entries[-1]
            last_mentorship_event = last_entry.get("event")
            last_mentorship_at = last_entry.get("timestamp") or last_entry.get(
                "resolved_at"
            )
        last_sidecast_phase = None
        last_sidecast_at = None
        if sidecast_entries:
            last_sidecast = sidecast_entries[-1]
            last_sidecast_phase = last_sidecast.get("phase")
            last_sidecast_at = last_sidecast.get("timestamp")
        sidecast_arc = None
        if sidecast_entries:
            sidecast_arc = sidecast_entries[-1].get("arc") or scholar.contract.get(
                "sidecast_arc"
            )
        history: List[Dict[str, object]] = []
        for entry in mentorship_entries[-3:]:
            history.append(
                {
                    "type": "mentorship",
                    "event": entry.get("event"),
                    "timestamp": entry.get("timestamp"),
                }
            )
        for entry in sidecast_entries[-3:]:
            history.append(
                {
                    "type": "sidecast",
                    "phase": entry.get("phase"),
                    "timestamp": entry.get("timestamp"),
                    "arc": entry.get("arc"),
                }
            )
        history.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        entries.append(
            {
                "scholar": scholar.name,
                "scholar_id": scholar.id,
                "feeling": feeling or 0.0,
                "active_mentorship": active_for_player,
                "track": scholar.career.get("track"),
                "tier": scholar.career.get("tier"),
                "last_mentorship_event": last_mentorship_event,
                "last_mentorship_at": last_mentorship_at,
                "sidecast_arc": sidecast_arc,
                "last_sidecast_phase": last_sidecast_phase,
                "last_sidecast_at": last_sidecast_at,
                "history": history[:5],
            }
        )
    entries.sort(key=lambda item: item["feeling"], reverse=True)
    if limit > 0:
        entries = entries[:limit]
    return entries


def commitment_summary(
    *,
    commitments: List[Dict[str, Any]],
    player,
    relationship_fn: Callable[[Any, str], float],
    limit: int = 10,
) -> List[Dict[str, object]]:
    """Summarize player commitments with relationship modifiers."""

    summary: List[Dict[str, object]] = []
    for entry in commitments:
        relationship = relationship_fn(player, entry.get("faction", ""))
        summary.append(
            {
                "id": entry.get("id"),
                "faction": entry.get("faction"),
                "tier": entry.get("tier"),
                "base_cost": entry.get("base_cost"),
                "start_at": entry.get("start_at"),
                "end_at": entry.get("end_at"),
                "status": entry.get("status"),
                "relationship_modifier": relationship,
                "last_processed_at": entry.get("last_processed_at"),
            }
        )
    summary.sort(key=lambda item: item.get("end_at") or 0)
    if limit > 0:
        summary = summary[:limit]
    return summary
