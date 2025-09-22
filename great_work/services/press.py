"""Press-related helper utilities.

Small, pure helpers used across services and adapters.
"""

from __future__ import annotations

from typing import Dict, List


def press_badges(metadata: Dict[str, object]) -> List[str]:
    """Derive descriptive badges for scheduled press metadata."""

    if not isinstance(metadata, dict):
        return []
    badges: List[str] = []
    source = metadata.get("source")
    if source == "sideways_followup":
        badges.append("Follow-Up")
    tags = metadata.get("tags")
    if isinstance(tags, (list, tuple)):
        badges.extend(str(tag) for tag in tags if tag)
    elif isinstance(tags, str) and tags:
        badges.append(tags)
    return badges


__all__ = ["press_badges"]

