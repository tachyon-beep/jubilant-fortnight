"""Expedition resolution rules and failure tables."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml

from .models import ExpeditionOutcome, ExpeditionPreparation, ExpeditionResult
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
            return ExpeditionResult(
                roll=roll,
                modifier=modifier,
                final_score=final,
                outcome=ExpeditionOutcome.PARTIAL,
                sideways_discovery=self._sideways_discovery(expedition_type, prep_depth),
            )
        if 65 <= final <= 84:
            return ExpeditionResult(
                roll=roll,
                modifier=modifier,
                final_score=final,
                outcome=ExpeditionOutcome.SUCCESS,
            )
        return ExpeditionResult(
            roll=roll,
            modifier=modifier,
            final_score=final,
            outcome=ExpeditionOutcome.LANDMARK,
            sideways_discovery=self._sideways_discovery(expedition_type, prep_depth, landmark=True),
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


__all__ = ["ExpeditionResolver", "FailureTables", "FailureResult"]
