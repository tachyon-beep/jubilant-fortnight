"""Scholar generation and lifecycle management."""
from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

from .models import MemoryFact, Scholar, ScholarStats
from .rng import DeterministicRNG

_DATA_PATH = Path(__file__).parent / "data"


class ScholarRepository:
    """Handles scholar templates and deterministic generation."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._path = data_path or _DATA_PATH
        self._base_scholars = self._load_yaml("scholars_base.yaml")["scholars"]
        self._namebanks = self._load_yaml("namebanks.yaml")["regions"]
        self._archetypes = self._load_yaml("archetypes.yaml")["archetypes"]
        self._disciplines = self._load_yaml("disciplines.yaml")["disciplines"]
        self._methods = self._load_yaml("methods.yaml")["methods"]
        self._drives = self._load_yaml("drives.yaml")["drives"]
        self._virtues = self._load_yaml("virtues.yaml")["virtues"]
        self._vices = self._load_yaml("vices.yaml")["vices"]
        self._taboos = self._load_yaml("taboos.yaml")["taboos"]

    def _load_yaml(self, name: str) -> Dict:
        with (self._path / name).open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def base_scholars(self) -> List[Scholar]:
        return [self.from_dict(item) for item in self._base_scholars]

    def from_dict(self, data: Dict) -> Scholar:
        stats = ScholarStats(**data["stats"])
        memory_data = data.get("memory")
        memory = None
        if memory_data:
            memory = self._deserialize_memory(memory_data)
        scholar = Scholar(
            id=data["id"],
            name=data["name"],
            seed=data["seed"],
            archetype=data["archetype"],
            disciplines=list(data["disciplines"]),
            methods=list(data["methods"]),
            drives=list(data["drives"]),
            virtues=list(data["virtues"]),
            vices=list(data["vices"]),
            stats=stats,
            politics=dict(data.get("politics", {})),
            catchphrase=data["catchphrase"],
            taboos=list(data["taboos"]),
            career=dict(data.get("career", {})),
            contract=dict(data.get("contract", {})),
        )
        if memory:
            scholar.memory = memory
        return scholar

    def _deserialize_memory(self, data: Dict):
        from .models import Memory

        facts = [
            MemoryFact(
                timestamp=datetime.fromisoformat(fact["t"]),
                type=fact["type"],
                subject=fact.get("who", ""),
                details={k: v for k, v in fact.items() if k not in {"t", "type", "who"}},
            )
            for fact in data.get("facts", [])
        ]
        memory = Memory(
            facts=facts,
            feelings=data.get("feelings", {}).get("players", {}),
            scars=list(data.get("scars", [])),
            decay=data.get("feelings", {}).get("decay", 0.98),
        )
        return memory

    def generate(self, rng: DeterministicRNG, identifier: str) -> Scholar:
        region = rng.choice(list(self._namebanks.keys()))
        given = rng.choice(self._namebanks[region]["given"])
        surname = rng.choice(self._namebanks[region]["surname"])
        name = f"Dr {given} {surname}"
        seed = rng.randint(1, 10_000_000)
        archetype = rng.choice(list(self._archetypes.keys()))
        disciplines = rng.sample(self._disciplines, 1 + rng.randint(0, 1))
        methods = rng.sample(self._methods, 2)
        drives = rng.sample(self._drives, 2)
        virtues = rng.sample(self._virtues, 2)
        vices = rng.sample(self._vices, 1)
        taboos = rng.sample(self._taboos, 1 + rng.randint(0, 1))
        stats = ScholarStats(
            talent=rng.randint(4, 9),
            reliability=rng.randint(2, 9),
            integrity=rng.randint(1, 9),
            theatrics=rng.randint(1, 9),
            loyalty=rng.randint(1, 9),
            risk=rng.randint(1, 9),
        )
        politics = {
            "academia": rng.randint(-3, 3),
            "government": rng.randint(-3, 3),
            "industry": rng.randint(-3, 3),
            "religion": rng.randint(-3, 3),
            "foreign": rng.randint(-3, 3),
        }
        catchphrase = rng.choice([
            "Show me {evidence} or I am not buying it.",
            "As I have long suspected, {topic} hinges on {concept}.",
            "Have we tried {reckless_method} yet?",
            "Bear with me. If {premise}, then {wild_leap}.",
        ])
        career = {"tier": "Postdoc", "track": "Academia"}
        contract = {"employer": "Independent", "term_years": rng.randint(1, 5)}
        scholar = Scholar(
            id=identifier,
            name=name,
            seed=seed,
            archetype=archetype,
            disciplines=disciplines,
            methods=methods,
            drives=drives,
            virtues=virtues,
            vices=vices,
            stats=stats,
            politics=politics,
            catchphrase=catchphrase,
            taboos=taboos,
            career=career,
            contract=contract,
        )
        return scholar

    def serialize(self, scholar: Scholar) -> Dict:
        data = asdict(scholar)
        data["stats"] = asdict(scholar.stats)
        data["memory"] = {
            "facts": [
                {
                    "t": fact.timestamp.isoformat(),
                    "type": fact.type,
                    "who": fact.subject,
                    **fact.details,
                }
                for fact in scholar.memory.facts
            ],
            "feelings": scholar.memory.feelings,
            "scars": scholar.memory.scars,
            "decay": scholar.memory.decay,
        }
        return data


def defection_probability(
    scholar: Scholar,
    offer_quality: float,
    mistreatment: float,
    alignment: float,
    plateau: float,
) -> float:
    """Implements the logistic defection curve from the design."""

    loyalty = scholar.loyalty_score()
    integrity = scholar.integrity_score()
    x = offer_quality + mistreatment + alignment + plateau - 0.6 * loyalty - 0.4 * integrity
    return 1.0 / (1.0 + math.exp(-6 * (x - 0.5)))


def apply_scar(scholar: Scholar, scar: str, subject: str, timestamp: datetime) -> None:
    """Adds a scar to the scholar's memory and reinforces feelings."""

    scholar.memory.add_scar(scar)
    scholar.memory.record_fact(
        MemoryFact(timestamp=timestamp, type="scar", subject=subject, details={"scar": scar})
    )
    scholar.memory.adjust_feeling(subject, -3.0)


__all__ = ["ScholarRepository", "defection_probability", "apply_scar"]
