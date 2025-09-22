"""Digest and upcoming highlights helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Tuple

from .press import press_badges


def upcoming_items_from_queue(
    queue: Iterable[Tuple[object, datetime, Dict[str, object]]],
    *,
    now: datetime,
    horizon_hours: int,
    limit: int,
) -> List[Dict[str, object]]:
    """Build a list of upcoming press items within the horizon.

    The queue contains tuples of (id, release_at, payload).
    """

    horizon = now + timedelta(hours=horizon_hours)
    items: List[Dict[str, object]] = []
    for _, release_at, payload in queue:
        if release_at > horizon:
            continue
        metadata = payload.get("metadata", {}) or {}
        items.append(
            {
                "headline": payload.get("headline", "Scheduled Update"),
                "type": payload.get("type", "scheduled_press"),
                "release_at": release_at,
                "metadata": metadata,
                "badges": press_badges(metadata),
            }
        )
    items.sort(key=lambda item: item["release_at"])
    return items[:limit]


def format_digest_highlights(
    items: List[Dict[str, object]],
    *,
    now: datetime,
    within_hours: int,
    tone_seed: Dict[str, object] | None,
) -> Tuple[str, str, List[Dict[str, object]]]:
    """Format headline, body, and metadata for digest highlights press."""

    headline_template = None
    callout = None
    blurb_template = None
    if tone_seed:
        headline_template = tone_seed.get("headline")
        callout = tone_seed.get("callout")
        blurb_template = tone_seed.get("blurb_template")

    headline = (
        headline_template.format(count=len(items))
        if headline_template
        else f"Upcoming Highlights ({len(items)})"
    )

    lines: List[str] = []
    metadata_items: List[Dict[str, object]] = []
    for item in items:
        release_at = item["release_at"]
        delta_minutes = max(0, int((release_at - now).total_seconds() // 60))
        if delta_minutes >= 60:
            hours = delta_minutes // 60
            minutes = delta_minutes % 60
            relative = f"{hours}h {minutes}m"
        else:
            relative = f"{delta_minutes}m"
        absolute = release_at.strftime("%Y-%m-%d %H:%M UTC")
        metadata = item.get("metadata", {})
        badges = press_badges(metadata)
        label_prefix = f"[{" | ".join(badges)}] " if badges else ""
        summary = f"{item['headline']} — {absolute} (in {relative})"
        if blurb_template:
            blurb = blurb_template.format(
                headline=item["headline"],
                relative_time=relative,
                call_to_action=callout or "",
            )
        else:
            blurb = summary
        if label_prefix:
            blurb = f"{label_prefix}{blurb}"
        lines.append(f"• {blurb}")
        metadata_items.append(
            {
                "headline": item["headline"],
                "type": item["type"],
                "release_at": release_at.isoformat(),
                "relative_minutes": delta_minutes,
                "badges": badges,
                "source": metadata.get("source"),
            }
        )

    if tone_seed and callout:
        lines.append(callout)

    base_body = "\n".join(lines)
    return headline, base_body, metadata_items


__all__ = ["upcoming_items_from_queue", "format_digest_highlights"]

