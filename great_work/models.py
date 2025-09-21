"""Core data models for The Great Work."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    cooldowns: Dict[str, int] = field(default_factory=dict)

    def adjust_reputation(self, delta: int, lower: int, upper: int) -> int:
        """Apply a reputation change while respecting configured bounds."""

        self.reputation = max(lower, min(upper, self.reputation + delta))
        return self.reputation

    def tick_cooldowns(self) -> None:
        """Advance any integer cooldown trackers by one step."""

        if not self.cooldowns:
            return
        for key, value in list(self.cooldowns.items()):
            next_value = max(0, value - 1)
            if next_value == 0:
                del self.cooldowns[key]
            else:
                self.cooldowns[key] = next_value


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
    sideways_effects: Optional[List["SidewaysEffect"]] = None


class SidewaysEffectType(str, Enum):
    """Types of mechanical effects that can be triggered by sideways discoveries."""
    FACTION_SHIFT = "faction_shift"
    SPAWN_THEORY = "spawn_theory"
    CREATE_GRUDGE = "create_grudge"
    QUEUE_ORDER = "queue_order"
    REPUTATION_CHANGE = "reputation_change"
    UNLOCK_OPPORTUNITY = "unlock_opportunity"


@dataclass
class SidewaysEffect:
    """Mechanical effect triggered by a sideways discovery."""
    effect_type: SidewaysEffectType
    description: str
    payload: Dict[str, object] = field(default_factory=dict)

    @staticmethod
    def faction_shift(faction: str, amount: int, description: str) -> "SidewaysEffect":
        """Create a faction influence shift effect."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.FACTION_SHIFT,
            description=description,
            payload={"faction": faction, "amount": amount}
        )

    @staticmethod
    def spawn_theory(theory_text: str, confidence: str, description: str) -> "SidewaysEffect":
        """Create a theory spawning effect."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.SPAWN_THEORY,
            description=description,
            payload={"theory": theory_text, "confidence": confidence}
        )

    @staticmethod
    def create_grudge(target_scholar_id: str, intensity: float, description: str) -> "SidewaysEffect":
        """Create a grudge between scholars."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.CREATE_GRUDGE,
            description=description,
            payload={"target": target_scholar_id, "intensity": intensity}
        )

    @staticmethod
    def queue_order(order_type: str, order_data: dict, description: str) -> "SidewaysEffect":
        """Queue a follow-up order."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.QUEUE_ORDER,
            description=description,
            payload={"order_type": order_type, "order_data": order_data}
        )

    @staticmethod
    def reputation_change(amount: int, description: str) -> "SidewaysEffect":
        """Change player reputation."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.REPUTATION_CHANGE,
            description=description,
            payload={"amount": amount}
        )

    @staticmethod
    def unlock_opportunity(opportunity_type: str, details: dict, description: str) -> "SidewaysEffect":
        """Unlock a special opportunity."""
        return SidewaysEffect(
            effect_type=SidewaysEffectType.UNLOCK_OPPORTUNITY,
            description=description,
            payload={"type": opportunity_type, "details": details}
        )


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


@dataclass
class PressRecord:
    timestamp: datetime
    release: PressRelease


@dataclass
class ExpeditionRecord:
    code: str
    player_id: str
    expedition_type: str
    objective: str
    team: List[str]
    funding: List[str]
    prep_depth: str
    confidence: str
    outcome: Optional[str] = None
    reputation_delta: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TheoryRecord:
    timestamp: datetime
    player_id: str
    theory: str
    confidence: str
    supporters: List[str]
    deadline: str


@dataclass
class OfferRecord:
    """Record of a defection offer or counter-offer."""
    id: Optional[int] = None
    scholar_id: str = ""
    faction: str = ""  # Target faction for defection
    rival_id: str = ""  # Player making the offer
    patron_id: str = ""  # Current patron of the scholar
    offer_type: str = "initial"  # initial, counter, final
    influence_offered: Dict[str, int] = field(default_factory=dict)
    terms: Dict[str, object] = field(default_factory=dict)  # Contract terms
    relationship_snapshot: Dict[str, object] = field(default_factory=dict)
    status: str = "pending"  # pending, accepted, rejected, countered
    parent_offer_id: Optional[int] = None  # For tracking negotiation chains
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


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
    "PressRecord",
    "ExpeditionRecord",
    "TheoryRecord",
    "OfferRecord",
]
