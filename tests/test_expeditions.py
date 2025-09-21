"""Tests for expedition resolver sideways integration."""

from __future__ import annotations

from great_work.expeditions import ExpeditionResolver
from great_work.models import ExpeditionPreparation, SidewaysEffectType
from great_work.rng import DeterministicRNG


def _build_resolver_with_vignette(tags):
    resolver = ExpeditionResolver()
    resolver._sideways_vignettes = {
        "field": {
            "shallow": [
                {
                    "id": "test_vignette",
                    "headline": "Test Headline",
                    "body": "Test body",
                    "gossip": ["Gossip"],
                    "tags": tags,
                }
            ]
        }
    }
    resolver._failure_tables.sideways = lambda expedition_type, depth: ["Mock discovery"]  # type: ignore[attr-defined]
    resolver._match_sideways_entry = lambda *args, **kwargs: None
    return resolver


def _resolve_with_roll(resolver: ExpeditionResolver, roll_value: int):
    rng = DeterministicRNG(seed=42)
    rng.roll_d100 = lambda: roll_value  # type: ignore[assignment]
    result = resolver.resolve(rng, ExpeditionPreparation(), "shallow", "field")
    assert result.sideways_effects, "Expected sideways effects"
    return result.sideways_effects or []


def test_archives_tag_spawns_theory():
    resolver = _build_resolver_with_vignette(["archives"])
    effects = _resolve_with_roll(resolver, 55)
    assert any(
        effect.effect_type == SidewaysEffectType.SPAWN_THEORY for effect in effects
    )


def test_diplomacy_tag_shifts_faction():
    resolver = _build_resolver_with_vignette(["diplomacy"])
    effects = _resolve_with_roll(resolver, 55)
    assert any(
        effect.effect_type == SidewaysEffectType.FACTION_SHIFT for effect in effects
    )


def test_industry_tag_unlocks_opportunity():
    resolver = _build_resolver_with_vignette(["industry"])
    effects = _resolve_with_roll(resolver, 55)
    assert any(
        effect.effect_type == SidewaysEffectType.UNLOCK_OPPORTUNITY
        for effect in effects
    )
