"""Moderation helper utilities.

Pure helpers to compute hashes, snippets, and messages for moderation flows.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..moderation import GuardianModerator, ModerationDecision


def compute_text_hash(text: str) -> str:
    """Compute a stable hash for moderation text content."""

    return GuardianModerator.compute_hash(text)


def snippet(text: str, *, limit: int = 140) -> str:
    """Build a single-line snippet for logs/notifications."""

    return text.strip().replace("\n", " ")[:limit]


def blocked_note(
    *,
    surface: str,
    actor_label: str,
    detail: str,
    text_hash: str,
    short_text: str,
    stage: str,
) -> str:
    """Format an admin note for blocked content events."""

    return (
        f"🛡️ Moderation blocked {surface} from {actor_label}: {detail}\n"
        f'hash={text_hash[:12]} stage={stage} snippet="{short_text}"'
    )


def build_moderation_event(
    *,
    severity: str,
    decision: ModerationDecision,
    text_hash: str,
    surface: str,
    actor: Optional[str],
    stage: str,
    text: str,
) -> Dict[str, Any]:
    """Construct a moderation event payload for logs and telemetry."""

    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc)
    data: Dict[str, Any] = {
        "timestamp": timestamp,
        "severity": severity,
        "surface": surface,
        "actor": actor,
        "stage": stage,
        "category": decision.category,
        "reason": decision.reason,
        "text_hash": text_hash,
        "metadata": decision.metadata or {},
        "snippet": snippet(text),
    }
    return data


__all__ = [
    "compute_text_hash",
    "snippet",
    "blocked_note",
    "build_moderation_event",
]

