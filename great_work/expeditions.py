"""Expedition resolution rules and failure tables."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import ExpeditionOutcome, ExpeditionPreparation, ExpeditionResult, SidewaysEffect
from .rng import DeterministicRNG

_DATA_PATH = Path(__file__).parent / "data"


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
                depth: list(entries)
                for depth, entries in depths.items()
            }

    def _load_yaml(self, name: str) -> Dict:
        with (self._path / name).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def roll(self, rng: DeterministicRNG, expedition_type: str, depth: str) -> FailureResult:
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
            discovery = self._sideways_discovery(expedition_type, prep_depth)
            effects = self._generate_sideways_effects(rng, discovery, expedition_type, prep_depth, False)
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
        discovery = self._sideways_discovery(expedition_type, prep_depth, landmark=True)
        effects = self._generate_sideways_effects(rng, discovery, expedition_type, prep_depth, True)
        return ExpeditionResult(
            roll=roll,
            modifier=modifier,
            final_score=final,
            outcome=ExpeditionOutcome.LANDMARK,
            sideways_discovery=discovery,
            sideways_effects=effects,
        )

    def _sideways_discovery(
        self, expedition_type: str, prep_depth: str, landmark: bool = False
    ) -> str | None:
        options = self._failure_tables.sideways(expedition_type, prep_depth)
        if not options:
            return None if not landmark else "New domain unlocked"
        if landmark:
            return options[-1]
        return options[0]

    def _generate_sideways_effects(
        self,
        rng: DeterministicRNG,
        discovery_text: Optional[str],
        expedition_type: str,
        prep_depth: str,
        is_landmark: bool
    ) -> Optional[List[SidewaysEffect]]:
        """Generate mechanical effects based on the sideways discovery text."""
        if not discovery_text:
            return None

        effects = []

        # Map discovery texts to specific mechanical effects
        if "coffeehouse gossip" in discovery_text.lower():
            # Think tank shallow: Gossip about forgotten thesis spawns theory
            effects.append(SidewaysEffect.spawn_theory(
                theory_text="A forgotten thesis resurfaces: The universe operates on hidden principles",
                confidence="suspect",
                description="Coffeehouse gossip spawns new theory"
            ))
            effects.append(SidewaysEffect.reputation_change(
                amount=1,
                description="Academic circles take notice"
            ))

        elif "symposium attendees demand" in discovery_text.lower():
            # Think tank deep: Follow-up colloquium creates faction opportunities
            effects.append(SidewaysEffect.faction_shift(
                faction="Academic",
                amount=2,
                description="Symposium demands create academic momentum"
            ))
            effects.append(SidewaysEffect.queue_order(
                order_type="conference",
                order_data={"topic": "emergency_colloquium", "auto_scheduled": True},
                description="Emergency colloquium scheduled"
            ))

        elif "local dignitaries offer" in discovery_text.lower():
            # Field shallow: Government influence opportunity
            effects.append(SidewaysEffect.faction_shift(
                faction="Government",
                amount=1,
                description="Local dignitaries show interest"
            ))
            effects.append(SidewaysEffect.unlock_opportunity(
                opportunity_type="dignitary_contract",
                details={"expires_in_days": 3, "influence_reward": 3},
                description="Provisional support contract available"
            ))

        elif "rival faction quietly invites" in discovery_text.lower():
            # Field deep: Joint stewardship creates complex dynamics
            faction = rng.choice(["Industry", "Religious", "Foreign"])
            effects.append(SidewaysEffect.faction_shift(
                faction=faction,
                amount=2,
                description=f"{faction} faction extends invitation"
            ))
            # Create a grudge with a random scholar who opposes this faction
            effects.append(SidewaysEffect.create_grudge(
                target_scholar_id="random",  # Service will pick a scholar
                intensity=0.5,
                description="Scholar opposes faction collaboration"
            ))

        elif "auditors flag" in discovery_text.lower():
            # Great project shallow: Innovation council review
            effects.append(SidewaysEffect.reputation_change(
                amount=-1,
                description="Auditors raise concerns"
            ))
            effects.append(SidewaysEffect.unlock_opportunity(
                opportunity_type="innovation_review",
                details={"deadline_days": 5, "success_reputation": 3},
                description="Innovation council review scheduled"
            ))

        elif "foreign observers float" in discovery_text.lower():
            # Great project deep: Transnational summit
            effects.append(SidewaysEffect.faction_shift(
                faction="Foreign",
                amount=3,
                description="International attention gained"
            ))
            effects.append(SidewaysEffect.queue_order(
                order_type="summit",
                order_data={"scope": "transnational", "prestige": "high"},
                description="Transnational summit proposed"
            ))

        elif "new domain unlocked" in discovery_text.lower():
            # Landmark discovery: Major breakthrough
            if is_landmark:
                # Landmark discoveries have bigger effects
                primary_faction = rng.choice(["Academic", "Government", "Industry", "Religious", "Foreign"])
                effects.append(SidewaysEffect.faction_shift(
                    faction=primary_faction,
                    amount=5,
                    description=f"Landmark discovery resonates with {primary_faction}"
                ))
                effects.append(SidewaysEffect.reputation_change(
                    amount=3,
                    description="Landmark achievement recognized"
                ))
                effects.append(SidewaysEffect.spawn_theory(
                    theory_text=f"New domain principles in {expedition_type} research",
                    confidence="certain",
                    description="Landmark spawns confident theory"
                ))

        return effects if effects else None


__all__ = ["ExpeditionResolver", "FailureTables", "FailureResult"]
