"""Expedition resolution rules and failure tables."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import (
    ExpeditionOutcome,
    ExpeditionPreparation,
    ExpeditionResult,
    SidewaysEffect,
    SidewaysEffectType,
)
from .rng import DeterministicRNG

_DATA_PATH = Path(__file__).parent / "data"
_SIDEWAYS_EFFECT_ENTRIES: Optional[List[Dict[str, Any]]] = None
_SIDEWAYS_VIGNETTES: Optional[Dict[str, Dict[str, List[Dict[str, Any]]]]] = None
_LANDMARK_PREPARATIONS: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None


_TAG_FALLBACKS: Dict[str, Dict[str, Any]] = {
    "archives": {
        "type": SidewaysEffectType.SPAWN_THEORY,
        "confidence": "suspect",
        "description": "Archive discoveries inspire a speculative thesis",
    },
    "diplomacy": {
        "type": SidewaysEffectType.FACTION_SHIFT,
        "faction": "Foreign",
        "amount": 2,
        "description": "Diplomatic ripples reach Foreign envoys",
    },
    "industry": {
        "type": SidewaysEffectType.UNLOCK_OPPORTUNITY,
        "opportunity": "industrial_contract",
        "details": {"expires_in_days": 4, "influence_gain": 2},
        "description": "Industrial partners float a lucrative contract",
    },
    "logistics": {
        "type": SidewaysEffectType.UNLOCK_OPPORTUNITY,
        "opportunity": "logistics_resupply",
        "details": {"expires_in_days": 3, "influence_gain": 1},
        "description": "Logistics teams open a resupply window",
    },
    "mentorship": {
        "type": SidewaysEffectType.UNLOCK_OPPORTUNITY,
        "opportunity": "mentorship_roundtable",
        "details": {"expires_in_days": 5, "reputation_bonus": 1},
        "description": "Mentorship council invites the expedition to a follow-up roundtable",
    },
    "culture": {
        "type": SidewaysEffectType.REPUTATION_CHANGE,
        "amount": 1,
        "description": "Cultural goodwill boosts academic standing",
    },
    "community": {
        "type": SidewaysEffectType.REPUTATION_CHANGE,
        "amount": 1,
        "description": "Community outreach improves reputation",
    },
    "environment": {
        "type": SidewaysEffectType.FACTION_SHIFT,
        "faction": "Religious",
        "amount": 1,
        "description": "Environmental stewards rally religious supporters",
    },
}


def _load_yaml_resource(filename: str) -> Dict[str, Any]:
    path = _DATA_PATH / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_sideways_effect_entries() -> List[Dict[str, Any]]:
    global _SIDEWAYS_EFFECT_ENTRIES
    if _SIDEWAYS_EFFECT_ENTRIES is None:
        data = _load_yaml_resource("sideways_effects.yaml")
        entries = data.get("sideways_effects", [])
        _SIDEWAYS_EFFECT_ENTRIES = entries if isinstance(entries, list) else []
    return _SIDEWAYS_EFFECT_ENTRIES


def _load_sideways_vignettes() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    global _SIDEWAYS_VIGNETTES
    if _SIDEWAYS_VIGNETTES is None:
        data = _load_yaml_resource("sideways_vignettes.yaml")
        if isinstance(data, dict):
            raw = data.get("vignettes", {})
            if isinstance(raw, dict):
                parsed: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
                for expedition_type, depths in raw.items():
                    if not isinstance(depths, dict):
                        continue
                    parsed[expedition_type] = {
                        depth: list(entries) if isinstance(entries, list) else []
                        for depth, entries in depths.items()
                    }
                _SIDEWAYS_VIGNETTES = parsed
            else:
                _SIDEWAYS_VIGNETTES = {}
        else:
            _SIDEWAYS_VIGNETTES = {}
    return _SIDEWAYS_VIGNETTES


def _load_landmark_preparations() -> Dict[str, Dict[str, Dict[str, Any]]]:
    global _LANDMARK_PREPARATIONS
    if _LANDMARK_PREPARATIONS is None:
        data = _load_yaml_resource("landmark_preparations.yaml")
        parsed: Dict[str, Dict[str, Dict[str, Any]]] = {}
        if isinstance(data, dict):
            root = data.get("landmark_preparations", {})
            if isinstance(root, dict):
                for expedition_type, depths in root.items():
                    if not isinstance(depths, dict):
                        continue
                    parsed[expedition_type] = {}
                    for depth, entry in depths.items():
                        if isinstance(entry, dict):
                            parsed[expedition_type][depth] = entry
        _LANDMARK_PREPARATIONS = parsed
    return _LANDMARK_PREPARATIONS


@dataclass
class FailureResult:
    weight: int
    result: str
    description: str


class FailureTables:
    def __init__(self, data_path: Path | None = None) -> None:
        self._path = data_path or _DATA_PATH
        data = self._load_yaml("failure_tables.yaml")
        raw_tables = data["failure_tables"]
        self._tables: Dict[str, Dict[str, List[FailureResult]]] = {}
        for expedition_type, depths in raw_tables.items():
            self._tables[expedition_type] = {
                depth: [FailureResult(**entry) for entry in entries]
                for depth, entries in depths.items()
            }
        self._sideways: Dict[str, Dict[str, List[str]]] = {}
        for expedition_type, depths in data.get("sideways", {}).items():
            self._sideways[expedition_type] = {
                depth: list(entries) for depth, entries in depths.items()
            }

    def _load_yaml(self, name: str) -> Dict:
        with (self._path / name).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def roll(
        self, rng: DeterministicRNG, expedition_type: str, depth: str
    ) -> FailureResult:
        table = self._tables[expedition_type][depth]
        total = sum(item.weight for item in table)
        roll = rng.randint(1, total)
        upto = 0
        for item in table:
            upto += item.weight
            if roll <= upto:
                return item
        return table[-1]

    def sideways(self, expedition_type: str, depth: str) -> List[str]:
        return self._sideways.get(expedition_type, {}).get(depth, [])


class ExpeditionResolver:
    """Resolves expedition outcomes according to the design spec."""

    def __init__(self, failure_tables: FailureTables | None = None) -> None:
        self._failure_tables = failure_tables or FailureTables()
        self._sideways_vignettes = _load_sideways_vignettes()

    def resolve(
        self,
        rng: DeterministicRNG,
        preparation: ExpeditionPreparation,
        prep_depth: str,
        expedition_type: str,
    ) -> ExpeditionResult:
        roll = rng.roll_d100()
        modifier = preparation.total_modifier()
        final = roll + modifier
        if final < 40:
            failure = self._failure_tables.roll(rng, expedition_type, prep_depth)
            return ExpeditionResult(
                roll=roll,
                modifier=modifier,
                final_score=final,
                outcome=ExpeditionOutcome.FAILURE,
                failure_detail=failure.description,
            )
        if 40 <= final <= 64:
            discovery = self._sideways_discovery(rng, expedition_type, prep_depth)
            effects = self._generate_sideways_effects(
                rng, discovery, expedition_type, prep_depth, False
            )
            return ExpeditionResult(
                roll=roll,
                modifier=modifier,
                final_score=final,
                outcome=ExpeditionOutcome.PARTIAL,
                sideways_discovery=discovery,
                sideways_effects=effects,
            )
        if 65 <= final <= 84:
            return ExpeditionResult(
                roll=roll,
                modifier=modifier,
                final_score=final,
                outcome=ExpeditionOutcome.SUCCESS,
            )
        discovery = self._sideways_discovery(
            rng, expedition_type, prep_depth, landmark=True
        )
        effects = self._generate_sideways_effects(
            rng, discovery, expedition_type, prep_depth, True
        )
        return ExpeditionResult(
            roll=roll,
            modifier=modifier,
            final_score=final,
            outcome=ExpeditionOutcome.LANDMARK,
            sideways_discovery=discovery,
            sideways_effects=effects,
        )

    def _sideways_discovery(
        self,
        rng: DeterministicRNG,
        expedition_type: str,
        prep_depth: str,
        landmark: bool = False,
    ) -> str | None:
        options = self._failure_tables.sideways(expedition_type, prep_depth)
        if not options and not landmark:
            return None
        if landmark:
            landmark_text = self._pick_landmark_discovery(
                rng, expedition_type, prep_depth
            )
            if landmark_text:
                return landmark_text
            if options:
                return options[-1]
            return "New domain unlocked"
        if len(options) == 1:
            return options[0]
        return rng.choice(options)

    def _pick_landmark_discovery(
        self,
        rng: DeterministicRNG,
        expedition_type: str,
        prep_depth: str,
    ) -> Optional[str]:
        preparations = _load_landmark_preparations()
        entry = preparations.get(expedition_type) or preparations.get("default")
        if not entry:
            return None

        depth_entry = (
            entry.get(prep_depth)
            or entry.get("standard")
            or next(
                (value for key, value in entry.items() if isinstance(value, dict)),
                None,
            )
        )
        if not isinstance(depth_entry, dict):
            return None

        discoveries = depth_entry.get("discoveries")
        if isinstance(discoveries, list) and discoveries:
            return rng.choice(discoveries)
        return None

    def _generate_sideways_effects(
        self,
        rng: DeterministicRNG,
        discovery_text: Optional[str],
        expedition_type: str,
        prep_depth: str,
        is_landmark: bool,
    ) -> Optional[List[SidewaysEffect]]:
        """Generate mechanical effects based on the sideways discovery text."""
        if not discovery_text:
            return None

        effects: List[SidewaysEffect] = []

        entry = self._match_sideways_entry(discovery_text, expedition_type, prep_depth)
        if entry is not None:
            effects.extend(
                self._build_sideways_effects_from_entry(
                    entry,
                    rng,
                    discovery_text,
                    expedition_type,
                    is_landmark,
                )
            )

        if not effects:
            text_lower = discovery_text.lower()
            if "new domain unlocked" in text_lower or is_landmark:
                self._append_default_landmark_effects(
                    effects,
                    rng,
                    expedition_type,
                )

        vignette = self._select_sideways_vignette(rng, expedition_type, prep_depth)
        if vignette:
            tags = vignette.get("tags", [])
            tag_effects = self._effects_from_tags(
                rng=rng,
                tags=tags,
                expedition_type=expedition_type,
                discovery_text=discovery_text,
            )
            for tag_effect in tag_effects:
                tag_effect.payload.setdefault("tags", tags)
            effects.extend(tag_effects)
            effects.append(
                SidewaysEffect.queue_order(
                    order_type="followup:sideways_vignette",
                    order_data={
                        "headline": vignette.get("headline"),
                        "body": vignette.get("body"),
                        "gossip": vignette.get("gossip", []),
                        "tags": tags,
                        "discovery": discovery_text,
                    },
                    description="Sideways vignette scheduled",
                )
            )

        return effects if effects else None

    def _append_default_landmark_effects(
        self,
        effects: List[SidewaysEffect],
        rng: DeterministicRNG,
        expedition_type: str,
    ) -> None:
        primary_faction = rng.choice(
            ["Academic", "Government", "Industry", "Religious", "Foreign"]
        )
        effects.append(
            SidewaysEffect.faction_shift(
                faction=primary_faction,
                amount=5,
                description=f"Landmark discovery resonates with {primary_faction}",
            )
        )
        effects.append(
            SidewaysEffect.reputation_change(
                amount=3,
                description="Landmark achievement recognized",
            )
        )
        effects.append(
            SidewaysEffect.spawn_theory(
                theory_text=f"New domain principles in {expedition_type} research",
                confidence="certain",
                description="Landmark spawns confident theory",
            )
        )

    def _match_sideways_entry(
        self,
        discovery_text: str,
        expedition_type: str,
        prep_depth: str,
    ) -> Optional[Dict[str, Any]]:
        if not discovery_text:
            return None
        text_lower = discovery_text.lower()
        for entry in _load_sideways_effect_entries():
            if not self._entry_applicable(entry, expedition_type, prep_depth):
                continue
            match_cfg = entry.get("match", {})
            contains = match_cfg.get("contains")
            if contains:
                if isinstance(contains, list):
                    if not all(str(item).lower() in text_lower for item in contains):
                        continue
                else:
                    if str(contains).lower() not in text_lower:
                        continue
            equals = match_cfg.get("equals")
            if equals:
                candidates = equals if isinstance(equals, list) else [equals]
                lowered = {str(option).lower() for option in candidates}
                if text_lower not in lowered:
                    continue
            return entry
        return None

    @staticmethod
    def _entry_applicable(
        entry: Dict[str, Any],
        expedition_type: str,
        prep_depth: str,
    ) -> bool:
        applies = entry.get("applies_to", {})
        allowed_types = applies.get("expedition_types")
        if allowed_types and expedition_type not in allowed_types:
            return False
        allowed_depths = applies.get("depths")
        if allowed_depths and prep_depth not in allowed_depths:
            return False
        return True

    def _build_sideways_effects_from_entry(
        self,
        entry: Dict[str, Any],
        rng: DeterministicRNG,
        discovery_text: str,
        expedition_type: str,
        is_landmark: bool,
    ) -> List[SidewaysEffect]:
        effects: List[SidewaysEffect] = []
        base_context = {
            "discovery": discovery_text,
            "expedition_type": expedition_type.replace("_", " "),
        }
        for spec in entry.get("effects", []):
            effect_type = spec.get("type")
            if not effect_type:
                continue
            try:
                effect_enum = SidewaysEffectType(effect_type)
            except ValueError:
                continue

            effect_context = dict(base_context)
            description_template = spec.get("description", "")

            if effect_enum == SidewaysEffectType.FACTION_SHIFT:
                faction = spec.get("faction")
                faction_choices = spec.get("faction_random")
                if faction_choices:
                    faction = rng.choice(faction_choices)
                if not faction:
                    continue
                effect_context["faction"] = faction
                amount = int(spec.get("amount", 0))
                description = description_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.faction_shift(
                        faction=faction, amount=amount, description=description
                    )
                )

            elif effect_enum == SidewaysEffectType.SPAWN_THEORY:
                theory_template = spec.get("theory")
                if not theory_template:
                    continue
                confidence = spec.get("confidence", "suspect")
                description = description_template.format(**effect_context)
                theory_text = theory_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.spawn_theory(
                        theory_text=theory_text,
                        confidence=confidence,
                        description=description,
                    )
                )

            elif effect_enum == SidewaysEffectType.CREATE_GRUDGE:
                target = spec.get("target", "random")
                intensity = float(spec.get("intensity", 0.5))
                description = description_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.create_grudge(
                        target_scholar_id=target,
                        intensity=intensity,
                        description=description,
                    )
                )

            elif effect_enum == SidewaysEffectType.QUEUE_ORDER:
                order_type = spec.get("order_type")
                if not order_type:
                    continue
                order_data = copy.deepcopy(spec.get("order_data", {}))
                description = description_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.queue_order(
                        order_type=order_type,
                        order_data=order_data,
                        description=description,
                    )
                )

            elif effect_enum == SidewaysEffectType.REPUTATION_CHANGE:
                amount = int(spec.get("amount", 0))
                description = description_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.reputation_change(
                        amount=amount, description=description
                    )
                )

            elif effect_enum == SidewaysEffectType.UNLOCK_OPPORTUNITY:
                opportunity_type = spec.get("opportunity_type")
                if not opportunity_type:
                    continue
                details = copy.deepcopy(spec.get("details", {}))
                description = description_template.format(**effect_context)
                effects.append(
                    SidewaysEffect.unlock_opportunity(
                        opportunity_type=opportunity_type,
                        details=details,
                        description=description,
                    )
                )

        tags = entry.get("tags")
        if tags:
            tag_list = list(tags) if isinstance(tags, list) else [tags]
            for effect in effects:
                effect.payload.setdefault("tags", tag_list)

        followups = entry.get("followups")
        if followups and effects:
            effects[0].payload.setdefault("followups", followups)

        return effects

    def _select_sideways_vignette(
        self,
        rng: DeterministicRNG,
        expedition_type: str,
        prep_depth: str,
    ) -> Optional[Dict[str, Any]]:
        """Select a narrative vignette for the expedition context."""

        type_vignettes = self._sideways_vignettes.get(expedition_type)
        if not type_vignettes:
            return None
        depth_entries = type_vignettes.get(prep_depth)
        if not depth_entries:
            return None
        if not depth_entries:
            return None
        return rng.choice(depth_entries)

    def _effects_from_tags(
        self,
        *,
        rng: DeterministicRNG,
        tags: List[str],
        expedition_type: str,
        discovery_text: Optional[str],
    ) -> List[SidewaysEffect]:
        effects: List[SidewaysEffect] = []
        if not tags:
            return effects
        seen = set()
        for tag in tags:
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            spec = _TAG_FALLBACKS.get(key)
            if not spec:
                continue
            effect_type = spec["type"]
            description = spec.get(
                "description", f"{tag.title()} ripple from expedition"
            )
            if effect_type == SidewaysEffectType.SPAWN_THEORY:
                theory_text = (
                    discovery_text
                    or f"{tag.title()} implications for {expedition_type}"
                )
                confidence = spec.get("confidence", "suspect")
                effects.append(
                    SidewaysEffect.spawn_theory(
                        theory_text=theory_text,
                        confidence=confidence,
                        description=description,
                    )
                )
            elif effect_type == SidewaysEffectType.FACTION_SHIFT:
                faction = spec.get("faction") or rng.choice(
                    [
                        "Academic",
                        "Government",
                        "Industry",
                        "Religious",
                        "Foreign",
                    ]
                )
                amount = int(spec.get("amount", 1))
                effects.append(
                    SidewaysEffect.faction_shift(
                        faction=faction,
                        amount=amount,
                        description=description,
                    )
                )
            elif effect_type == SidewaysEffectType.UNLOCK_OPPORTUNITY:
                opportunity_type = spec.get("opportunity", f"{key}_opportunity")
                details = dict(spec.get("details", {}))
                if "expires_in_days" not in details:
                    details["expires_in_days"] = 3
                effects.append(
                    SidewaysEffect.unlock_opportunity(
                        opportunity_type=opportunity_type,
                        details=details,
                        description=description,
                    )
                )
            elif effect_type == SidewaysEffectType.REPUTATION_CHANGE:
                amount = int(spec.get("amount", 1))
                effects.append(
                    SidewaysEffect.reputation_change(
                        amount=amount,
                        description=description,
                    )
                )
            elif effect_type == SidewaysEffectType.QUEUE_ORDER:
                order_type = spec.get("order_type", f"followup:{key}")
                payload = {
                    "tags": tags,
                    "discovery": discovery_text,
                    "scope": expedition_type,
                }
                effects.append(
                    SidewaysEffect.queue_order(
                        order_type=order_type,
                        order_data=payload,
                        description=description,
                    )
                )
        return effects


__all__ = ["ExpeditionResolver", "FailureTables", "FailureResult"]
