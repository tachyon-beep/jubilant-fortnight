"""High-level game service orchestrating commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .config import Settings, get_settings
from .expeditions import ExpeditionResolver, FailureTables
from .models import (
    ConfidenceLevel,
    Event,
    ExpeditionOutcome,
    ExpeditionPreparation,
    ExpeditionRecord,
    MemoryFact,
    Player,
    PressRecord,
    PressRelease,
    TheoryRecord,
)
from .press import (
    BulletinContext,
    GossipContext,
    OutcomeContext,
    ExpeditionContext,
    RecruitmentContext,
    DefectionContext,
    academic_bulletin,
    academic_gossip,
    defection_notice,
    discovery_report,
    recruitment_report,
    retraction_notice,
    research_manifesto,
)
from .rng import DeterministicRNG
from .scholars import ScholarRepository, apply_scar, defection_probability
from .state import GameState


@dataclass
class ExpeditionOrder:
    code: str
    player_id: str
    expedition_type: str
    objective: str
    team: List[str]
    funding: List[str]
    preparation: ExpeditionPreparation
    prep_depth: str
    confidence: ConfidenceLevel
    timestamp: datetime


class GameService:
    """Coordinates between state, RNG and generators."""

    _MIN_SCHOLAR_ROSTER = 20
    _MAX_SCHOLAR_ROSTER = 30
    _EXPEDITION_COSTS: Dict[str, Dict[str, int]] = {
        "think_tank": {"academia": 1},
        "field": {"academia": 1, "government": 1},
        "great_project": {"academia": 2, "government": 2, "industry": 2},
    }

    _EXPEDITION_REWARDS: Dict[str, Dict[str, int]] = {
        "think_tank": {"academia": 1},
        "field": {"government": 1, "industry": 1},
        "great_project": {"academia": 2, "industry": 2, "foreign": 1},
    }
    _FACTIONS: Tuple[str, ...] = ("academia", "government", "industry", "religion", "foreign")

    _CAREER_TRACKS: Dict[str, List[str]] = {
        "Academia": ["Postdoc", "Fellow", "Professor"],
        "Industry": ["Associate", "Director", "Visionary"],
    }
    _CAREER_TICKS_REQUIRED = 3
    _FOLLOWUP_DELAYS: Dict[str, timedelta] = {
        "defection_grudge": timedelta(days=2),
        "defection_return": timedelta(days=3),
        "recruitment_grudge": timedelta(days=1),
    }

    def __init__(
        self,
        db_path: Path,
        settings: Settings | None = None,
        repository: ScholarRepository | None = None,
        failure_tables: FailureTables | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or ScholarRepository()
        self.state = GameState(
            db_path,
            repository=self.repository,
            start_year=self.settings.timeline_start_year,
        )
        self.resolver = ExpeditionResolver(failure_tables or FailureTables())
        self._rng = DeterministicRNG(seed=42)
        self._pending_expeditions: Dict[str, ExpeditionOrder] = {}
        self._generated_counter = self._initial_generated_counter()
        if not any(True for _ in self.state.all_scholars()):
            self.state.seed_base_scholars()
        self._ensure_roster()

    # Player helpers ----------------------------------------------------
    def ensure_player(self, player_id: str, display_name: Optional[str] = None) -> None:
        player = self.state.get_player(player_id)
        if player:
            self._ensure_influence_structure(player)
            self.state.upsert_player(player)
            return
        display = display_name or player_id
        self.state.upsert_player(
            player=Player(
                id=player_id,
                display_name=display,
                reputation=0,
                influence={faction: 0 for faction in self._FACTIONS},
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
        now = datetime.now(timezone.utc)
        self.state.append_event(
            Event(
                timestamp=now,
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
        self.state.record_theory(
            TheoryRecord(
                timestamp=now,
                player_id=player_id,
                theory=theory,
                confidence=confidence.value,
                supporters=supporters,
                deadline=deadline,
            )
        )
        self._archive_press(press, now)
        return press

    def queue_expedition(
        self,
        code: str,
        player_id: str,
        expedition_type: str,
        objective: str,
        team: List[str],
        funding: List[str],
        preparation: ExpeditionPreparation,
        prep_depth: str,
        confidence: ConfidenceLevel,
    ) -> PressRelease:
        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        assert player is not None
        self._require_reputation(player, f"expedition_{expedition_type}")
        self._apply_expedition_costs(player, expedition_type, funding)
        self.state.upsert_player(player)
        order = ExpeditionOrder(
            code=code,
            player_id=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
            preparation=preparation,
            prep_depth=prep_depth,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
        )
        self._pending_expeditions[code] = order
        record = ExpeditionRecord(
            code=code,
            player_id=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
            prep_depth=prep_depth,
            confidence=confidence.value,
            timestamp=order.timestamp,
        )
        self.state.record_expedition(record)
        self.state.append_event(
            Event(
                timestamp=order.timestamp,
                action="launch_expedition",
                payload={
                    "code": code,
                    "player": player_id,
                    "type": expedition_type,
                    "objective": objective,
                    "team": team,
                    "funding": funding,
                    "prep_depth": prep_depth,
                    "confidence": confidence.value,
                },
            )
        )
        ctx = ExpeditionContext(
            code=code,
            player=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
        )
        press = research_manifesto(ctx)
        self._archive_press(press, order.timestamp)
        return press

    def resolve_pending_expeditions(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        for code, order in list(self._pending_expeditions.items()):
            result = self.resolver.resolve(
                self._rng, order.preparation, order.prep_depth, order.expedition_type
            )
            delta = self._confidence_delta(order.confidence, result.outcome)
            player = self.state.get_player(order.player_id)
            assert player is not None
            new_reputation = self._apply_reputation_change(player, delta, order.confidence)
            self.state.upsert_player(player)
            reactions = self._generate_reactions(order.team, result)
            ctx = OutcomeContext(
                code=code,
                player=order.player_id,
                expedition_type=order.expedition_type,
                result=result,
                reputation_change=delta,
                reactions=reactions,
            )
            if result.outcome == ExpeditionOutcome.FAILURE:
                release = retraction_notice(ctx)
            else:
                release = discovery_report(ctx)
            releases.append(release)
            now = datetime.now(timezone.utc)
            self._archive_press(release, now)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="expedition_resolved",
                    payload={
                        "code": code,
                        "player": order.player_id,
                        "type": order.expedition_type,
                        "result": result.outcome.value,
                        "roll": result.roll,
                        "modifier": result.modifier,
                        "final": result.final_score,
                        "confidence": order.confidence.value,
                        "reputation_delta": delta,
                        "reputation_after": new_reputation,
                    },
                )
            )
            record = ExpeditionRecord(
                code=order.code,
                player_id=order.player_id,
                expedition_type=order.expedition_type,
                objective=order.objective,
                team=order.team,
                funding=order.funding,
                prep_depth=order.prep_depth,
                confidence=order.confidence.value,
                outcome=result.outcome.value,
                reputation_delta=delta,
                timestamp=order.timestamp,
            )
            self.state.record_expedition(
                record,
                result_payload={
                    "roll": result.roll,
                    "modifier": result.modifier,
                    "final": result.final_score,
                    "sideways": result.sideways_discovery,
                    "failure": result.failure_detail,
                },
            )
            self._apply_expedition_rewards(player, order.expedition_type, result)
            self.state.upsert_player(player)
            self._update_relationships_from_result(order, result)
            sidecast = self._maybe_spawn_sidecast(order, result)
            if sidecast:
                releases.append(sidecast)
                self._archive_press(sidecast, now)
            del self._pending_expeditions[code]
        return releases

    # Public actions ----------------------------------------------------
    def attempt_recruitment(
        self,
        player_id: str,
        scholar_id: str,
        faction: str,
        base_chance: float = 0.6,
    ) -> Tuple[bool, PressRelease]:
        """Attempt to recruit a scholar, applying cooldown and influence effects."""

        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        scholar = self.state.get_scholar(scholar_id)
        if not player or not scholar:
            raise ValueError("Unknown player or scholar")

        self._require_reputation(player, "recruitment")
        influence_bonus = max(0, player.influence.get(faction, 0)) * 0.05
        cooldown_penalty = 0.5 if player.cooldowns.get("recruitment", 0) else 1.0
        chance = max(0.05, min(0.95, base_chance * cooldown_penalty + influence_bonus))
        roll = self._rng.uniform(0.0, 1.0)
        success = roll < chance
        now = datetime.now(timezone.utc)
        player.cooldowns["recruitment"] = max(2, player.cooldowns.get("recruitment", 0))

        if success:
            scholar.memory.adjust_feeling(player_id, 2.0)
            scholar.contract["employer"] = player_id
            scholar.contract["faction"] = faction
            self._apply_influence_change(player, faction, 1)
            press = recruitment_report(
                RecruitmentContext(
                    player=player_id,
                    scholar=scholar.name,
                    outcome="success",
                    chance=chance,
                    faction=faction,
                )
            )
        else:
            scholar.memory.adjust_feeling(player_id, -1.0)
            press = recruitment_report(
                RecruitmentContext(
                    player=player_id,
                    scholar=scholar.name,
                    outcome="failure",
                    chance=chance,
                    faction=faction,
                )
            )
            resolve_at = now + self._FOLLOWUP_DELAYS["recruitment_grudge"]
            self.state.schedule_followup(
                scholar_id,
                "recruitment_grudge",
                resolve_at,
                {"player": player_id, "faction": faction},
            )
        self.state.save_scholar(scholar)
        self.state.upsert_player(player)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="recruitment_attempt",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "faction": faction,
                    "chance": chance,
                    "success": success,
                },
            )
        )
        return success, press

    def evaluate_defection_offer(
        self,
        scholar_id: str,
        offer_quality: float,
        mistreatment: float,
        alignment: float,
        plateau: float,
        new_faction: str,
    ) -> Tuple[bool, PressRelease]:
        """Resolve a public defection offer and archive the resulting press."""

        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError("Unknown scholar")

        probability = defection_probability(scholar, offer_quality, mistreatment, alignment, plateau)
        roll = self._rng.uniform(0.0, 1.0)
        timestamp = datetime.now(timezone.utc)
        if roll < probability:
            former_employer = scholar.contract.get("employer", "their patron")
            apply_scar(scholar, "defection", former_employer, timestamp)
            scholar.contract["employer"] = new_faction
            scholar.memory.adjust_feeling(former_employer, -4.0)
            outcome = "defected"
            press = defection_notice(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="defected",
                    new_faction=new_faction,
                    probability=probability,
                )
            )
            resolve_at = timestamp + self._FOLLOWUP_DELAYS["defection_return"]
            self.state.schedule_followup(
                scholar_id,
                "defection_return",
                resolve_at,
                {"former_employer": former_employer, "new_faction": new_faction},
            )
        else:
            scholar.memory.adjust_feeling(new_faction, -2.0)
            outcome = "refused"
            press = defection_notice(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="refused",
                    new_faction=new_faction,
                    probability=probability,
                )
            )
            resolve_at = timestamp + self._FOLLOWUP_DELAYS["defection_grudge"]
            self.state.schedule_followup(
                scholar_id,
                "defection_grudge",
                resolve_at,
                {"faction": new_faction, "probability": probability},
            )
        self.state.save_scholar(scholar)
        self._archive_press(press, timestamp)
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="defection_evaluated",
                payload={
                    "scholar": scholar_id,
                    "probability": probability,
                    "roll": roll,
                    "outcome": outcome,
                    "new_faction": new_faction,
                },
            )
        )
        return outcome == "defected", press

    def player_status(self, player_id: str) -> Dict[str, object]:
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")
        self._ensure_influence_structure(player)
        cap = self._influence_cap(player)
        thresholds = {
            action: value for action, value in self.settings.action_thresholds.items()
        }
        return {
            "player": player.display_name,
            "reputation": player.reputation,
            "influence": dict(player.influence),
            "influence_cap": cap,
            "cooldowns": dict(player.cooldowns),
            "thresholds": thresholds,
        }

    def export_press_archive(self, limit: int = 10, offset: int = 0) -> List[PressRecord]:
        return self.state.list_press_releases(limit=limit, offset=offset)

    def export_log(self, limit: int = 20) -> Dict[str, Iterable[object]]:
        events = self.state.export_events()
        press = self.state.list_press_releases(limit=limit)
        return {"events": events[-limit:], "press": press}

    def advance_digest(self) -> List[PressRelease]:
        """Advance the digest tick, decaying cooldowns and maintaining the roster."""

        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        years_elapsed, current_year = self.state.advance_timeline(
            now, self.settings.time_scale_days_per_year
        )
        if years_elapsed:
            timeline_press = PressRelease(
                type="timeline_update",
                headline=f"The year turns to {current_year}",
                body=(
                    "The Gazette notes the turning of the year. "
                    f"{years_elapsed} year(s) slip into history and the calendar now reads {current_year}."
                ),
                metadata={
                    "current_year": current_year,
                    "years_elapsed": years_elapsed,
                },
            )
            self._archive_press(timeline_press, now)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="timeline_advanced",
                    payload={
                        "current_year": current_year,
                        "years_elapsed": years_elapsed,
                    },
                )
            )
            releases.append(timeline_press)
        for player in list(self.state.all_players()):
            player.tick_cooldowns()
            self.state.upsert_player(player)
        self._ensure_roster()
        releases.extend(self._progress_careers())
        releases.extend(self._resolve_followups())
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

    # Internal helpers --------------------------------------------------
    def _archive_press(self, press: PressRelease, timestamp: datetime) -> None:
        self.state.record_press_release(PressRecord(timestamp=timestamp, release=press))

    def _initial_generated_counter(self) -> int:
        max_index = 0
        for scholar in self.state.all_scholars():
            if scholar.id.startswith("s.proc-"):
                try:
                    _, value = scholar.id.split("proc-")
                    max_index = max(max_index, int(value))
                except ValueError:
                    continue
        return max_index + 1

    def _ensure_roster(self) -> None:
        scholars = list(self.state.all_scholars())
        while len(scholars) < self._MIN_SCHOLAR_ROSTER:
            identifier = f"s.proc-{self._generated_counter:03d}"
            self._generated_counter += 1
            scholar = self.repository.generate(self._rng, identifier)
            self.state.save_scholar(scholar)
            scholars.append(scholar)
            self.state.append_event(
                Event(
                    timestamp=datetime.now(timezone.utc),
                    action="scholar_spawned",
                    payload={"id": scholar.id, "name": scholar.name, "origin": "roster_fill"},
                )
            )
        if len(scholars) <= self._MAX_SCHOLAR_ROSTER:
            return
        surplus = len(scholars) - self._MAX_SCHOLAR_ROSTER
        ranked = sorted(
            scholars,
            key=lambda s: (
                0 if s.contract.get("employer") == "Independent" else 1,
                s.stats.loyalty,
                len(s.memory.facts),
            ),
        )
        for scholar in ranked[:surplus]:
            self.state.remove_scholar(scholar.id)
            self.state.append_event(
                Event(
                    timestamp=datetime.now(timezone.utc),
                    action="scholar_retired",
                    payload={"id": scholar.id, "name": scholar.name},
                )
            )

    def _progress_careers(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        for scholar in list(self.state.all_scholars()):
            track = scholar.career.get("track", "Academia")
            ladder = self._CAREER_TRACKS.get(track, self._CAREER_TRACKS["Academia"])
            tier = scholar.career.get("tier", ladder[0])
            ticks = int(scholar.career.get("ticks", 0)) + 1
            scholar.career["ticks"] = ticks
            if tier not in ladder:
                ladder = self._CAREER_TRACKS["Academia"]
                tier = ladder[0]
                scholar.career["tier"] = tier
            idx = ladder.index(tier)
            if idx < len(ladder) - 1 and ticks >= self._CAREER_TICKS_REQUIRED:
                scholar.career["tier"] = ladder[idx + 1]
                scholar.career["ticks"] = 0
                quote = f"Advanced to {scholar.career['tier']} after diligent mentorship."
                press = academic_gossip(
                    GossipContext(scholar=scholar.name, quote=quote, trigger="Digest advancement"),
                )
                releases.append(press)
                self._archive_press(press, now)
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="career_progression",
                        payload={"scholar": scholar.id, "new_tier": scholar.career["tier"]},
                    )
                )
            self.state.save_scholar(scholar)
        return releases

    def _resolve_followups(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        for followup_id, scholar_id, kind, payload in self.state.due_followups(now):
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                self.state.clear_followup(followup_id)
                continue
            if kind == "defection_grudge":
                scholar.memory.adjust_feeling(payload.get("faction", "Unknown"), -1.5)
                quote = "The betrayal still smolders in the halls."
            elif kind == "defection_return":
                scholar.memory.adjust_feeling(payload.get("former_employer", "Unknown"), 1.0)
                quote = "Rumours swirl about a tentative reconciliation."
            elif kind == "recruitment_grudge":
                scholar.memory.adjust_feeling(payload.get("player", "Unknown"), -1.0)
                quote = "The slighted scholar sharpens their public retort."
            else:
                quote = "An unresolved thread lingers in the archives."
            press = academic_gossip(
                GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=kind.replace("_", " ").title(),
                )
            )
            self._archive_press(press, now)
            releases.append(press)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="followup_resolved",
                    payload={"scholar": scholar.id, "kind": kind},
                )
            )
            self.state.save_scholar(scholar)
            self.state.clear_followup(followup_id)
        return releases

    def _apply_reputation_change(
        self, player: Player, delta: int, confidence: ConfidenceLevel
    ) -> int:
        bounds = self.settings.reputation_bounds
        new_value = player.adjust_reputation(delta, bounds["min"], bounds["max"])
        if confidence is ConfidenceLevel.STAKE_CAREER:
            player.cooldowns["recruitment"] = max(2, player.cooldowns.get("recruitment", 0))
        return new_value

    def _apply_expedition_costs(self, player: Player, expedition_type: str, funding: List[str]) -> None:
        costs = self._EXPEDITION_COSTS.get(expedition_type, {})
        for faction, amount in costs.items():
            self._apply_influence_change(player, faction, -amount)
        for faction in funding:
            self._apply_influence_change(player, faction, 1)

    def _apply_expedition_rewards(
        self, player: Player, expedition_type: str, result
    ) -> None:
        if result.outcome == ExpeditionOutcome.FAILURE:
            return
        rewards = self._EXPEDITION_REWARDS.get(expedition_type, {})
        for faction, amount in rewards.items():
            self._apply_influence_change(player, faction, amount)

    def _update_relationships_from_result(self, order: ExpeditionOrder, result) -> None:
        outcome = result.outcome
        for scholar_id in order.team:
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue
            if outcome == ExpeditionOutcome.FAILURE:
                scholar.memory.adjust_feeling(order.player_id, -2.0)
            else:
                scholar.memory.adjust_feeling(order.player_id, 1.0)
            self.state.save_scholar(scholar)
            feeling = scholar.memory.feelings.get(order.player_id, 0.0)
            self.state.update_relationship(scholar_id, order.player_id, feeling)

    def _maybe_spawn_sidecast(self, order: ExpeditionOrder, result) -> Optional[PressRelease]:
        if result.outcome == ExpeditionOutcome.FAILURE:
            return None
        if sum(1 for _ in self.state.all_scholars()) >= self._MAX_SCHOLAR_ROSTER:
            return None
        identifier = f"s.proc-{self._generated_counter:03d}"
        self._generated_counter += 1
        scholar = self.repository.generate(self._rng, identifier)
        scholar.memory.record_fact(
            MemoryFact(
                timestamp=datetime.now(timezone.utc),
                type="sidecast",
                subject=order.player_id,
                details={"expedition": order.code},
            )
        )
        scholar.contract["employer"] = order.player_id
        self.state.save_scholar(scholar)
        ctx = GossipContext(
            scholar=scholar.name,
            quote="I saw the expedition and could not resist joining.",
            trigger=f"Expedition {order.code}",
        )
        press = academic_gossip(ctx)
        self.state.append_event(
            Event(
                timestamp=datetime.now(timezone.utc),
                action="scholar_sidecast",
                payload={"scholar": scholar.id, "expedition": order.code},
            )
        )
        return press

    def _generate_reactions(self, team: List[str], result) -> List[str]:
        reactions = []
        for scholar_id in team:
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue
            tone = "thrilled" if result.outcome in {ExpeditionOutcome.SUCCESS, ExpeditionOutcome.LANDMARK} else "wary"
            phrase = scholar.catchphrase.format(
                evidence="evidence",
                topic="the work",
                concept="collaboration",
                reckless_method="dynamite",
                premise="the data holds",
                wild_leap="we can fly",
            )
            reactions.append(f"{scholar.name} ({tone}): {phrase}")
        return reactions

    def _ensure_influence_structure(self, player: Player) -> None:
        for faction in self._FACTIONS:
            player.influence.setdefault(faction, 0)
        if player.cooldowns is None:
            player.cooldowns = {}

    def _apply_influence_change(self, player: Player, faction: str, delta: int) -> int:
        self._ensure_influence_structure(player)
        current = player.influence.get(faction, 0)
        cap = self._influence_cap(player)
        new_value = current + delta
        if delta > 0:
            new_value = min(cap, new_value)
        player.influence[faction] = new_value
        return new_value

    def _influence_cap(self, player: Player) -> int:
        base = int(self.settings.influence_caps.get("base", 5))
        per_rep = float(self.settings.influence_caps.get("per_reputation", 0.0))
        dynamic = base + int(per_rep * max(0, player.reputation))
        return max(base, dynamic)

    def _require_reputation(self, player: Player, action: str) -> None:
        threshold = self.settings.action_thresholds.get(action)
        if threshold is None:
            return
        if player.reputation < threshold:
            raise PermissionError(
                f"Action '{action}' requires reputation {threshold} but {player.display_name} has {player.reputation}."
            )

__all__ = ["GameService", "ExpeditionOrder"]
