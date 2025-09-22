"""Sidecast helpers."""

from __future__ import annotations

from ..press import GossipContext, academic_gossip


def phase_delta(phase: str) -> float:
    mapping = {
        "spawn": 0.75,
        "debut": 1.0,
        "integration": 0.6,
        "spotlight": 1.2,
    }
    return mapping.get(phase, 0.4)


def build_spawn_press(*, scholar_name: str, expedition_code: str):
    ctx = GossipContext(
        scholar=scholar_name,
        quote="I saw the expedition and could not resist joining.",
        trigger=f"Expedition {expedition_code}",
    )
    return academic_gossip(ctx)


__all__ = ["phase_delta", "build_spawn_press"]

