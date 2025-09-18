"""High-level game service orchestrating commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import Settings, get_settings
from .expeditions import ExpeditionResolver, FailureTables
from .models import (
    ConfidenceLevel,
    Event,
    ExpeditionOutcome,
    ExpeditionPreparation,
    Player,
    PressRelease,
)
from .press import (
    BulletinContext,
    OutcomeContext,
    ExpeditionContext,
    academic_bulletin,
    discovery_report,
    research_manifesto,
)
from .rng import DeterministicRNG
from .scholars import ScholarRepository
from .state import GameState


@dataclass
class ExpeditionOrder:
    code: str
    player_id: str
    objective: str
    team: List[str]
    funding: List[str]
    preparation: ExpeditionPreparation
    prep_depth: str
    confidence: ConfidenceLevel
    timestamp: datetime


class GameService:
    """Coordinates between state, RNG and generators."""

    def __init__(
        self,
        db_path: Path,
        settings: Settings | None = None,
        repository: ScholarRepository | None = None,
        failure_tables: FailureTables | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or ScholarRepository()
        self.state = GameState(db_path, repository=self.repository)
        self.resolver = ExpeditionResolver(failure_tables or FailureTables())
        self._rng = DeterministicRNG(seed=42)
        self._pending_expeditions: Dict[str, ExpeditionOrder] = {}
        if not any(True for _ in self.state.all_scholars()):
            self.state.seed_base_scholars()

    # Player helpers ----------------------------------------------------
    def ensure_player(self, player_id: str, display_name: Optional[str] = None) -> None:
        player = self.state.get_player(player_id)
        if player:
            return
        display = display_name or player_id
        self.state.upsert_player(
            player=Player(
                id=player_id,
                display_name=display,
                reputation=0,
                influence={
                    "academia": 0,
                    "government": 0,
                    "industry": 0,
                    "religion": 0,
                    "foreign": 0,
                },
            )
        )

    def submit_theory(
        self,
        player_id: str,
        theory: str,
        confidence: ConfidenceLevel,
        supporters: List[str],
        deadline: str,
    ) -> PressRelease:
        self.ensure_player(player_id)
        ctx = BulletinContext(
            bulletin_number=len(self.state.export_events()) + 1,
            player=player_id,
            theory=theory,
            confidence=confidence.value,
            supporters=supporters,
            deadline=deadline,
        )
        press = academic_bulletin(ctx)
        self.state.append_event(
            Event(
                timestamp=datetime.utcnow(),
                action="submit_theory",
                payload={
                    "player": player_id,
                    "theory": theory,
                    "confidence": confidence.value,
                    "supporters": supporters,
                    "deadline": deadline,
                },
            )
        )
        return press

    def queue_expedition(
        self,
        code: str,
        player_id: str,
        objective: str,
        team: List[str],
        funding: List[str],
        preparation: ExpeditionPreparation,
        prep_depth: str,
        confidence: ConfidenceLevel,
    ) -> PressRelease:
        self.ensure_player(player_id)
        order = ExpeditionOrder(
            code=code,
            player_id=player_id,
            objective=objective,
            team=team,
            funding=funding,
            preparation=preparation,
            prep_depth=prep_depth,
            confidence=confidence,
            timestamp=datetime.utcnow(),
        )
        self._pending_expeditions[code] = order
        self.state.append_event(
            Event(
                timestamp=order.timestamp,
                action="launch_expedition",
                payload={
                    "code": code,
                    "player": player_id,
                    "objective": objective,
                    "team": team,
                    "funding": funding,
                    "prep_depth": prep_depth,
                    "confidence": confidence.value,
                },
            )
        )
        ctx = ExpeditionContext(code=code, player=player_id, objective=objective, team=team, funding=funding)
        return research_manifesto(ctx)

    def resolve_pending_expeditions(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        for code, order in list(self._pending_expeditions.items()):
            result = self.resolver.resolve(self._rng, order.preparation, order.prep_depth)
            delta = self._confidence_delta(order.confidence, result.outcome)
            ctx = OutcomeContext(
                code=code,
                player=order.player_id,
                result=result,
                reputation_change=delta,
                reactions=self._generate_reactions(order.team, result),
            )
            releases.append(discovery_report(ctx))
            self.state.append_event(
                Event(
                    timestamp=datetime.utcnow(),
                    action="expedition_resolved",
                    payload={
                        "code": code,
                        "player": order.player_id,
                        "result": result.outcome.value,
                        "roll": result.roll,
                        "modifier": result.modifier,
                        "final": result.final_score,
                        "confidence": order.confidence.value,
                        "reputation_delta": delta,
                    },
                )
            )
            del self._pending_expeditions[code]
        return releases

    def _confidence_delta(self, confidence: ConfidenceLevel, outcome: ExpeditionOutcome) -> int:
        wagers = self.settings.confidence_wagers
        table = wagers[confidence.value]
        success_states = {ExpeditionOutcome.SUCCESS, ExpeditionOutcome.LANDMARK}
        if outcome in success_states:
            return table["reward"]
        if outcome == ExpeditionOutcome.PARTIAL:
            return max(1, table["reward"] // 2)
        return table["penalty"]

    def _generate_reactions(self, team: List[str], result) -> List[str]:
        reactions = []
        for scholar_id in team:
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue
            phrase = scholar.catchphrase.format(
                evidence="evidence",
                topic="the work",
                concept="collaboration",
                reckless_method="dynamite",
                premise="the data holds",
                wild_leap="we can fly",
            )
            reactions.append(f"{scholar.name}: {phrase}")
        return reactions


__all__ = ["GameService", "ExpeditionOrder"]
