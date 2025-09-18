"""Core data models for The Great Work."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class ConfidenceLevel(str, Enum):
    SUSPECT = "suspect"
    CERTAIN = "certain"
    STAKE_CAREER = "stake_my_career"


@dataclass
class Feeling:
    target_id: str
    intensity: float
    kind: str


@dataclass
class MemoryFact:
    timestamp: datetime
    type: str
    subject: str
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class Memory:
    facts: List[MemoryFact] = field(default_factory=list)
    feelings: Dict[str, float] = field(default_factory=dict)
    scars: List[str] = field(default_factory=list)
    decay: float = 0.98

    def record_fact(self, fact: MemoryFact) -> None:
        self.facts.append(fact)

    def adjust_feeling(self, key: str, delta: float) -> None:
        self.feelings[key] = self.feelings.get(key, 0.0) + delta

    def add_scar(self, scar: str) -> None:
        if scar not in self.scars:
            self.scars.append(scar)

    def decay_feelings(self) -> None:
        for key, value in list(self.feelings.items()):
            if key in self.scars:
                continue
            new_value = value * self.decay
            if abs(new_value) < 0.01:
                del self.feelings[key]
            else:
                self.feelings[key] = new_value


@dataclass
class ScholarStats:
    talent: int
    reliability: int
    integrity: int
    theatrics: int
    loyalty: int
    risk: int


@dataclass
class Scholar:
    id: str
    name: str
    seed: int
    archetype: str
    disciplines: List[str]
    methods: List[str]
    drives: List[str]
    virtues: List[str]
    vices: List[str]
    stats: ScholarStats
    politics: Dict[str, int]
    catchphrase: str
    taboos: List[str]
    memory: Memory = field(default_factory=Memory)
    career: Dict[str, str] = field(default_factory=dict)
    contract: Dict[str, str] = field(default_factory=dict)

    def loyalty_score(self) -> float:
        return self.stats.loyalty / 10.0

    def integrity_score(self) -> float:
        return self.stats.integrity / 10.0


@dataclass
class Player:
    id: str
    display_name: str
    reputation: int = 0
    influence: Dict[str, int] = field(default_factory=dict)


@dataclass
class ExpeditionPreparation:
    think_tank_bonus: int = 0
    expertise_bonus: int = 0
    site_friction: int = 0
    political_friction: int = 0

    def total_modifier(self) -> int:
        return (
            self.think_tank_bonus
            + self.expertise_bonus
            + self.site_friction
            + self.political_friction
        )


class ExpeditionOutcome(str, Enum):
    FAILURE = "failure"
    PARTIAL = "partial"
    SUCCESS = "success"
    LANDMARK = "landmark"


@dataclass
class ExpeditionResult:
    roll: int
    modifier: int
    final_score: int
    outcome: ExpeditionOutcome
    failure_detail: Optional[str] = None
    sideways_discovery: Optional[str] = None


@dataclass
class Event:
    timestamp: datetime
    action: str
    payload: Dict[str, object]


@dataclass
class PressRelease:
    type: str
    headline: str
    body: str
    metadata: Dict[str, object] = field(default_factory=dict)


__all__ = [
    "ConfidenceLevel",
    "Scholar",
    "ScholarStats",
    "Memory",
    "MemoryFact",
    "Player",
    "ExpeditionPreparation",
    "ExpeditionResult",
    "ExpeditionOutcome",
    "Event",
    "PressRelease",
]
