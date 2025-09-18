"""Expedition resolution rules and failure tables."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

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
        self._tables = {
            key: [FailureResult(**entry) for entry in entries]
            for key, entries in data["failure_tables"].items()
        }

    def _load_yaml(self, name: str) -> Dict:
        with (self._path / name).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def roll(self, rng: DeterministicRNG, depth: str) -> FailureResult:
        table = self._tables[depth]
        total = sum(item.weight for item in table)
        roll = rng.randint(1, total)
        upto = 0
        for item in table:
            upto += item.weight
            if roll <= upto:
                return item
        return table[-1]


class ExpeditionResolver:
    """Resolves expedition outcomes according to the design spec."""

    def __init__(self, failure_tables: FailureTables | None = None) -> None:
        self._failure_tables = failure_tables or FailureTables()

    def resolve(
        self,
        rng: DeterministicRNG,
        preparation: ExpeditionPreparation,
        prep_depth: str,
    ) -> ExpeditionResult:
        roll = rng.roll_d100()
        modifier = preparation.total_modifier()
        final = roll + modifier
        if final < 40:
            failure = self._failure_tables.roll(rng, prep_depth)
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
                sideways_discovery=self._sideways_discovery(prep_depth),
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
            sideways_discovery="New domain unlocked",
        )

    def _sideways_discovery(self, prep_depth: str) -> str | None:
        if prep_depth == "shallow":
            return "Minor clue toward adjacent site"
        if prep_depth == "deep":
            return "Adjacent-field discovery that shifts focus"
        return None


__all__ = ["ExpeditionResolver", "FailureTables", "FailureResult"]
