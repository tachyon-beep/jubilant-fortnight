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
    OfferRecord,
    Player,
    PressRecord,
    PressRelease,
    SidewaysEffect,
    SidewaysEffectType,
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
            # Apply sideways discovery effects if present
            if result.sideways_effects:
                effect_releases = self._apply_sideways_effects(order, result, player)
                releases.extend(effect_releases)
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

    # ===== New Offer System Methods =====
    def create_defection_offer(
        self,
        rival_id: str,
        scholar_id: str,
        target_faction: str,
        influence_offer: Dict[str, int],
        terms: Optional[Dict[str, object]] = None,
    ) -> Tuple[int, List[PressRelease]]:
        """Create a new defection offer to poach a scholar.

        Returns:
            (offer_id, press_releases) tuple
        """
        timestamp = datetime.now(timezone.utc)
        scholar = self.state.get_scholar(scholar_id)
        rival = self.state.get_player(rival_id)

        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")
        if not rival:
            raise ValueError(f"Player {rival_id} not found")

        # Find current patron
        patron_id = scholar.contract.get("employer", "")
        if not patron_id:
            raise ValueError(f"Scholar {scholar_id} has no current employer")

        # Validate rival has enough influence
        for faction, amount in influence_offer.items():
            if rival.influence.get(faction, 0) < amount:
                raise ValueError(f"Player {rival_id} has insufficient {faction} influence")

        # Create the offer record
        offer = OfferRecord(
            scholar_id=scholar_id,
            faction=target_faction,
            rival_id=rival_id,
            patron_id=patron_id,
            offer_type="initial",
            influence_offered=influence_offer,
            terms=terms or {},
            status="pending",
            created_at=timestamp,
        )

        offer_id = self.state.save_offer(offer)
        offer.id = offer_id

        # Schedule followup for offer evaluation (24 hour negotiation window)
        resolve_at = timestamp + timedelta(hours=24)
        self.state.schedule_followup(
            scholar_id,
            "evaluate_offer",
            resolve_at,
            {"offer_id": offer_id},
        )

        # Generate press releases
        press = []
        headline = f"Poaching Attempt: {rival.display_name} Targets {scholar.name}"
        body = f"{rival.display_name} has made an offer to {scholar.name} to join {target_faction}.\n"
        body += f"The offer includes: {', '.join(f'{v} {k}' for k, v in influence_offer.items())} influence.\n"
        if terms:
            body += f"Additional terms: {terms}\n"
        body += f"Current patron {patron_id} has 24 hours to counter."

        release = PressRelease(
            type="negotiation",
            headline=headline,
            body=body,
            metadata={
                "offer_id": offer_id,
                "rival": rival_id,
                "patron": patron_id,
                "scholar": scholar_id,
            }
        )
        self._archive_press(release, timestamp)
        press.append(release)

        # Deduct influence from rival (held in escrow)
        for faction, amount in influence_offer.items():
            rival.influence[faction] -= amount
        self.state.upsert_player(rival)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="offer_created",
                payload={
                    "offer_id": offer_id,
                    "rival": rival_id,
                    "scholar": scholar_id,
                    "influence": influence_offer,
                }
            )
        )

        return offer_id, press

    def counter_offer(
        self,
        player_id: str,
        original_offer_id: int,
        counter_influence: Dict[str, int],
        counter_terms: Optional[Dict[str, object]] = None,
    ) -> Tuple[int, List[PressRelease]]:
        """Create a counter-offer to retain a scholar.

        Returns:
            (counter_offer_id, press_releases) tuple
        """
        timestamp = datetime.now(timezone.utc)
        original = self.state.get_offer(original_offer_id)
        player = self.state.get_player(player_id)

        if not original:
            raise ValueError(f"Offer {original_offer_id} not found")
        if not player:
            raise ValueError(f"Player {player_id} not found")

        # Verify this player is the current patron
        if player_id != original.patron_id:
            raise ValueError(f"Player {player_id} is not the current patron")

        # Verify offer is still pending
        if original.status != "pending":
            raise ValueError(f"Offer {original_offer_id} is not pending (status: {original.status})")

        # Validate patron has enough influence
        for faction, amount in counter_influence.items():
            if player.influence.get(faction, 0) < amount:
                raise ValueError(f"Player {player_id} has insufficient {faction} influence")

        # Create counter-offer
        counter = OfferRecord(
            scholar_id=original.scholar_id,
            faction=original.faction,  # Keep same target faction for consistency
            rival_id=original.rival_id,
            patron_id=player_id,
            offer_type="counter",
            influence_offered=counter_influence,
            terms=counter_terms or {},
            status="pending",
            parent_offer_id=original_offer_id,
            created_at=timestamp,
        )

        counter_id = self.state.save_offer(counter)
        counter.id = counter_id

        # Update original offer status
        self.state.update_offer_status(original_offer_id, "countered")

        # Reschedule followup for counter evaluation (12 hours for final round)
        self.state.clear_followup(original_offer_id)  # Clear original followup
        resolve_at = timestamp + timedelta(hours=12)
        self.state.schedule_followup(
            original.scholar_id,
            "evaluate_counter",
            resolve_at,
            {"counter_offer_id": counter_id},
        )

        # Generate press
        scholar = self.state.get_scholar(original.scholar_id)
        press = []
        headline = f"Counter-Offer: {player.display_name} Fights for {scholar.name}"
        body = f"{player.display_name} has countered with: {', '.join(f'{v} {k}' for k, v in counter_influence.items())} influence.\n"
        if counter_terms:
            body += f"Additional terms: {counter_terms}\n"
        body += f"The rival has 12 hours to make a final offer."

        release = PressRelease(
            type="negotiation",
            headline=headline,
            body=body,
            metadata={
                "counter_offer_id": counter_id,
                "original_offer_id": original_offer_id,
            }
        )
        self._archive_press(release, timestamp)
        press.append(release)

        # Deduct influence from patron (held in escrow)
        for faction, amount in counter_influence.items():
            player.influence[faction] -= amount
        self.state.upsert_player(player)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="counter_offer_created",
                payload={
                    "counter_offer_id": counter_id,
                    "original_offer_id": original_offer_id,
                    "patron": player_id,
                    "influence": counter_influence,
                }
            )
        )

        return counter_id, press

    def evaluate_scholar_offer(self, offer_id: int) -> float:
        """Calculate a scholar's likelihood to accept an offer based on feelings and terms.

        Returns probability between 0.0 and 1.0
        """
        offer = self.state.get_offer(offer_id)
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        scholar = self.state.get_scholar(offer.scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {offer.scholar_id} not found")

        # Base probability from offer quality (influence amount)
        total_influence = sum(offer.influence_offered.values())
        offer_quality = min(10.0, total_influence / 10.0)  # Scale to 0-10

        # Check feelings toward rival and patron
        rival_feeling = scholar.memory.feelings.get(offer.rival_id, 0.0)
        patron_feeling = scholar.memory.feelings.get(offer.patron_id, 0.0)

        # Mistreatment factor (negative feelings toward current patron)
        mistreatment = max(0.0, -patron_feeling) / 5.0  # Scale negative feelings

        # Alignment factor (positive feelings toward rival)
        alignment = max(0.0, rival_feeling) / 5.0

        # Check for plateau (no recent discoveries)
        recent_discoveries = [
            fact for fact in scholar.memory.facts
            if fact.kind == "discovery" and
            (datetime.now(timezone.utc) - fact.when).days < 90
        ]
        plateau = 0.0 if recent_discoveries else 2.0

        # Use existing defection probability calculation
        from .scholars import defection_probability
        probability = defection_probability(scholar, offer_quality, mistreatment, alignment, plateau)

        # Adjust for contract terms
        if "exclusive_research" in offer.terms:
            probability += 0.1
        if "guaranteed_funding" in offer.terms:
            probability += 0.15
        if "leadership_role" in offer.terms:
            probability += 0.2

        # Adjust for offer type (counters have slight advantage)
        if offer.offer_type == "counter":
            probability -= 0.1  # Loyalty bonus to current patron

        return min(1.0, max(0.0, probability))

    def resolve_offer_negotiation(
        self,
        offer_id: int,
    ) -> List[PressRelease]:
        """Resolve a negotiation chain and determine the final outcome.

        This is called by the scheduler when negotiations time out.
        """
        timestamp = datetime.now(timezone.utc)
        offer_chain = self.state.get_offer_chain(offer_id)

        if not offer_chain:
            raise ValueError(f"No offer chain found for {offer_id}")

        # Find the best offer in the chain
        best_offer = None
        best_probability = 0.0

        for offer in offer_chain:
            if offer.status == "pending":
                prob = self.evaluate_scholar_offer(offer.id)
                if prob > best_probability:
                    best_probability = prob
                    best_offer = offer

        if not best_offer:
            # No valid offers, scholar stays
            press = []
            for offer in offer_chain:
                self.state.update_offer_status(offer.id, "expired", timestamp)
                # Return escrowed influence
                player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                for faction, amount in offer.influence_offered.items():
                    player.influence[faction] += amount
                self.state.upsert_player(player)
            return press

        # Roll for acceptance
        roll = self._rng.uniform(0.0, 1.0)
        scholar = self.state.get_scholar(best_offer.scholar_id)
        press = []

        if roll < best_probability:
            # Scholar accepts the offer
            winner_id = best_offer.rival_id if best_offer.offer_type == "initial" else best_offer.patron_id
            loser_id = best_offer.patron_id if best_offer.offer_type == "initial" else best_offer.rival_id

            # Transfer scholar
            old_employer = scholar.contract.get("employer", "")
            scholar.contract["employer"] = best_offer.faction if best_offer.offer_type == "initial" else old_employer

            # Apply emotional consequences
            from .scholars import apply_scar
            if best_offer.offer_type == "initial":
                # Defection - apply scar and negative feelings
                apply_scar(scholar, "defection", old_employer, timestamp)
                scholar.memory.adjust_feeling(old_employer, -4.0)
                scholar.memory.adjust_feeling(winner_id, 2.0)
            else:
                # Stayed with patron - positive feelings
                scholar.memory.adjust_feeling(winner_id, 3.0)
                scholar.memory.adjust_feeling(loser_id, -2.0)

            self.state.save_scholar(scholar)

            # Create press release
            headline = f"{scholar.name} {'Defects to' if best_offer.offer_type == 'initial' else 'Remains with'} {winner_id}"
            body = f"After intense negotiations, {scholar.name} has chosen to {'join' if best_offer.offer_type == 'initial' else 'remain with'} {winner_id}.\n"
            body += f"Winning offer: {', '.join(f'{v} {k}' for k, v in best_offer.influence_offered.items())} influence.\n"
            body += f"Probability of acceptance was {best_probability:.1%}."

            release = PressRelease(
                type="negotiation_resolved",
                headline=headline,
                body=body,
                metadata={
                    "scholar": scholar.id,
                    "winner": winner_id,
                    "loser": loser_id,
                    "offer_id": best_offer.id,
                }
            )
            self._archive_press(release, timestamp)
            press.append(release)

            # Mark all offers as resolved
            for offer in offer_chain:
                status = "accepted" if offer.id == best_offer.id else "rejected"
                self.state.update_offer_status(offer.id, status, timestamp)

            # Return escrowed influence for losing offers
            for offer in offer_chain:
                if offer.id != best_offer.id:
                    player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                    for faction, amount in offer.influence_offered.items():
                        player.influence[faction] += amount
                    self.state.upsert_player(player)

            # Winner pays the influence cost (already deducted)
            # No need to return it

            # Schedule followup for potential return (if defected)
            if best_offer.offer_type == "initial":
                resolve_at = timestamp + self._FOLLOWUP_DELAYS.get("defection_return", timedelta(days=30))
                self.state.schedule_followup(
                    scholar.id,
                    "defection_return",
                    resolve_at,
                    {"former_employer": old_employer, "new_faction": best_offer.faction},
                )

        else:
            # Scholar rejects all offers
            headline = f"{scholar.name} Rejects All Offers"
            body = f"{scholar.name} has decided to remain with their current patron.\n"
            body += f"Best offer had {best_probability:.1%} chance of success but failed."

            release = PressRelease(
                type="negotiation_resolved",
                headline=headline,
                body=body,
                metadata={
                    "scholar": scholar.id,
                    "all_rejected": True,
                }
            )
            self._archive_press(release, timestamp)
            press.append(release)

            # Mark all offers as rejected and return influence
            for offer in offer_chain:
                self.state.update_offer_status(offer.id, "rejected", timestamp)
                player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                for faction, amount in offer.influence_offered.items():
                    player.influence[faction] += amount
                self.state.upsert_player(player)

            # Adjust feelings
            scholar.memory.adjust_feeling(best_offer.rival_id, -1.0)
            self.state.save_scholar(scholar)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="negotiation_resolved",
                payload={
                    "offer_chain": [o.id for o in offer_chain],
                    "best_offer": best_offer.id if best_offer else None,
                    "probability": best_probability,
                    "roll": roll,
                    "accepted": roll < best_probability,
                }
            )
        )

        return press

    def list_player_offers(self, player_id: str) -> List[OfferRecord]:
        """Get all active offers involving a player."""
        return self.state.list_active_offers(player_id)

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

    def queue_mentorship(
        self,
        player_id: str,
        scholar_id: str,
        career_track: str | None = None,
    ) -> PressRelease:
        """Queue a mentorship for the next digest resolution."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        # Check if scholar already has an active mentorship
        existing = self.state.get_active_mentorship(scholar_id)
        if existing:
            raise ValueError(f"Scholar {scholar_id} already has an active mentor")

        # Queue the mentorship
        mentorship_id = self.state.add_mentorship(player_id, scholar_id, career_track)

        # Generate press release
        quote = f"I shall guide {scholar.name} towards greater achievements."
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Mentorship of {scholar.name}",
            )
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="mentorship_queued",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "career_track": career_track,
                    "mentorship_id": mentorship_id,
                },
            )
        )

        return press

    def assign_lab(
        self,
        player_id: str,
        scholar_id: str,
        career_track: str,
    ) -> PressRelease:
        """Assign a scholar to a new career track (Academia or Industry)."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        if career_track not in self._CAREER_TRACKS:
            raise ValueError(f"Invalid career track: {career_track}. Choose from {list(self._CAREER_TRACKS.keys())}")

        # Check if player is mentoring this scholar
        mentorship = self.state.get_active_mentorship(scholar_id)
        if not mentorship or mentorship[1] != player_id:
            raise ValueError(f"You must be actively mentoring {scholar.name} to assign their lab")

        # Update scholar's career track
        old_track = scholar.career.get("track", "Academia")
        scholar.career["track"] = career_track

        # Reset to first tier of new track if changing tracks
        if old_track != career_track:
            scholar.career["tier"] = self._CAREER_TRACKS[career_track][0]
            scholar.career["ticks"] = 0

        self.state.save_scholar(scholar)

        # Generate press release
        quote = f"{scholar.name} has been assigned to the {career_track} track under my mentorship."
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Lab assignment for {scholar.name}",
            )
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="lab_assigned",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "career_track": career_track,
                    "old_track": old_track,
                },
            )
        )

        return press

    def launch_conference(
        self,
        player_id: str,
        theory_id: int,
        confidence: ConfidenceLevel,
        supporters: List[str],
        opposition: List[str],
    ) -> PressRelease:
        """Queue a conference to debate a theory with public reputation stakes."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        # Check if theory exists
        theory_data = self.state.get_theory_by_id(theory_id)
        if not theory_data:
            raise ValueError(f"Theory {theory_id} not found")
        _, theory = theory_data

        # Generate unique conference code
        code = f"CONF-{self._rng.randint(1000, 9999)}"

        # Validate supporters and opposition are scholars
        all_scholars = {s.id for s in self.state.all_scholars()}
        for scholar_id in supporters:
            if scholar_id not in all_scholars:
                raise ValueError(f"Scholar {scholar_id} not found")
        for scholar_id in opposition:
            if scholar_id not in all_scholars:
                raise ValueError(f"Scholar {scholar_id} not found")

        # Queue the conference
        self.state.add_conference(
            code=code,
            player_id=player_id,
            theory_id=theory_id,
            confidence=confidence.value,
            supporters=supporters,
            opposition=opposition,
        )

        # Generate press release
        supporter_names = [s.name for s in self.state.all_scholars() if s.id in supporters]
        opposition_names = [s.name for s in self.state.all_scholars() if s.id in opposition]

        quote = f"Conference {code} announced to debate: {theory.theory}"
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Conference on theory #{theory_id}",
            )
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="conference_launched",
                payload={
                    "code": code,
                    "player": player_id,
                    "theory_id": theory_id,
                    "confidence": confidence.value,
                    "supporters": supporters,
                    "opposition": opposition,
                },
            )
        )

        return press

    def resolve_conferences(self) -> List[PressRelease]:
        """Resolve all pending conferences during digest."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)

        for code, player_id, theory_id, confidence_str, supporters, opposition in self.state.get_pending_conferences():
            player = self.state.get_player(player_id)
            if not player:
                continue

            theory_data = self.state.get_theory_by_id(theory_id)
            if not theory_data:
                continue
            _, theory = theory_data

            confidence = ConfidenceLevel(confidence_str)

            # Simple resolution: roll d100 with modifiers based on support
            base_roll = self._rng.randint(1, 100)
            support_modifier = len(supporters) * 5
            opposition_modifier = len(opposition) * 5
            final_roll = base_roll + support_modifier - opposition_modifier

            # Determine outcome based on roll
            if final_roll >= 60:
                outcome = ExpeditionOutcome.SUCCESS
            elif final_roll >= 40:
                outcome = ExpeditionOutcome.PARTIAL
            else:
                outcome = ExpeditionOutcome.FAILURE

            # Apply reputation changes
            reputation_delta = self._confidence_delta(confidence, outcome)
            player.adjust_reputation(
                reputation_delta,
                self.settings.reputation_bounds["min"],
                self.settings.reputation_bounds["max"],
            )
            self.state.upsert_player(player)

            # Resolve the conference
            self.state.resolve_conference(
                code=code,
                outcome=outcome.value,
                reputation_delta=reputation_delta,
                result_payload={
                    "roll": base_roll,
                    "support_modifier": support_modifier,
                    "opposition_modifier": opposition_modifier,
                    "final_roll": final_roll,
                },
            )

            # Generate press release
            outcome_text = {
                ExpeditionOutcome.SUCCESS: "The conference concluded with resounding support for the theory",
                ExpeditionOutcome.PARTIAL: "The conference ended with mixed opinions",
                ExpeditionOutcome.FAILURE: "The conference thoroughly rejected the theory",
            }[outcome]

            quote = f"Conference {code} result: {outcome_text}. Reputation change: {reputation_delta:+d}"
            press = academic_gossip(
                GossipContext(
                    scholar="The Academy",
                    quote=quote,
                    trigger=f"Conference {code} resolution",
                )
            )

            releases.append(press)
            self._archive_press(press, now)

            self.state.append_event(
                Event(
                    timestamp=now,
                    action="conference_resolved",
                    payload={
                        "code": code,
                        "outcome": outcome.value,
                        "reputation_delta": reputation_delta,
                        "final_roll": final_roll,
                    },
                )
            )

        return releases

    def start_symposium(self, topic: str, description: str) -> PressRelease:
        """Start a new symposium with the given topic."""
        now = datetime.now(timezone.utc)

        # Resolve any previous symposium first
        current = self.state.get_current_symposium_topic()
        if current:
            self.resolve_symposium()

        # Create new symposium topic
        topic_id = self.state.create_symposium_topic(
            symposium_date=now,
            topic=topic,
            description=description,
        )

        # Generate press release
        press = PressRelease(
            type="symposium_announcement",
            headline=f"Symposium Topic: {topic}",
            body=(
                f"The Academy announces this week's symposium topic: {topic}\n\n"
                f"{description}\n\n"
                "Cast your votes with /symposium_vote:\n"
                "Option 1: Support the proposition\n"
                "Option 2: Oppose the proposition\n"
                "Option 3: Call for further study"
            ),
            metadata={"topic_id": topic_id, "topic": topic},
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_started",
                payload={"topic_id": topic_id, "topic": topic},
            )
        )

        return press

    def vote_symposium(self, player_id: str, vote_option: int) -> PressRelease:
        """Record a player's vote on the current symposium topic."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        current = self.state.get_current_symposium_topic()
        if not current:
            raise ValueError("No symposium is currently active")

        topic_id, topic, description, options = current

        if vote_option not in options:
            raise ValueError(f"Invalid vote option. Choose from {options}")

        # Record the vote
        self.state.record_symposium_vote(topic_id, player_id, vote_option)

        # Generate press release
        vote_text = {
            1: "supports the proposition",
            2: "opposes the proposition",
            3: "calls for further study",
        }[vote_option]

        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=f"I {vote_text} regarding {topic}.",
                trigger="Symposium vote",
            )
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_vote",
                payload={
                    "player": player_id,
                    "topic_id": topic_id,
                    "vote_option": vote_option,
                },
            )
        )

        return press

    def resolve_symposium(self) -> PressRelease:
        """Resolve the current symposium and announce the results."""
        current = self.state.get_current_symposium_topic()
        if not current:
            return PressRelease(
                type="symposium_notice",
                headline="No Active Symposium",
                body="There is no symposium currently requiring resolution.",
                metadata={},
            )

        topic_id, topic, description, _ = current
        votes = self.state.get_symposium_votes(topic_id)

        # Determine winner
        if not votes:
            winner_text = "No consensus (no votes received)"
            winner = "none"
        else:
            winner_option = max(votes.keys(), key=lambda x: votes.get(x, 0))
            winner_count = votes[winner_option]
            total_votes = sum(votes.values())
            winner_text = {
                1: f"The proposition is supported ({winner_count}/{total_votes} votes)",
                2: f"The proposition is opposed ({winner_count}/{total_votes} votes)",
                3: f"Further study is required ({winner_count}/{total_votes} votes)",
            }[winner_option]
            winner = str(winner_option)

        # Resolve the topic
        self.state.resolve_symposium_topic(topic_id, winner)

        # Generate press release
        press = PressRelease(
            type="symposium_resolution",
            headline=f"Symposium Resolved: {topic}",
            body=(
                f"The symposium on '{topic}' has concluded.\n\n"
                f"Result: {winner_text}\n\n"
                "The Academy thanks all participants for their thoughtful contributions."
            ),
            metadata={
                "topic_id": topic_id,
                "topic": topic,
                "winner": winner,
                "votes": votes,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_resolved",
                payload={
                    "topic_id": topic_id,
                    "winner": winner,
                    "votes": votes,
                },
            )
        )

        return press

    # Admin tools ---------------------------------------------------
    def admin_adjust_reputation(
        self,
        admin_id: str,
        player_id: str,
        delta: int,
        reason: str,
    ) -> PressRelease:
        """Admin command to adjust a player's reputation."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        old_reputation = player.reputation
        player.adjust_reputation(
            delta,
            self.settings.reputation_bounds["min"],
            self.settings.reputation_bounds["max"],
        )
        self.state.upsert_player(player)

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline=f"Administrative Reputation Adjustment",
            body=(
                f"Player {player.display_name}'s reputation adjusted by {delta:+d} "
                f"(from {old_reputation} to {player.reputation})\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}"
            ),
            metadata={
                "admin": admin_id,
                "player": player_id,
                "delta": delta,
                "reason": reason,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_reputation_adjustment",
                payload={
                    "admin": admin_id,
                    "player": player_id,
                    "delta": delta,
                    "old": old_reputation,
                    "new": player.reputation,
                    "reason": reason,
                },
            )
        )

        return press

    def admin_adjust_influence(
        self,
        admin_id: str,
        player_id: str,
        faction: str,
        delta: int,
        reason: str,
    ) -> PressRelease:
        """Admin command to adjust a player's influence."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        if faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {faction}")

        self._ensure_influence_structure(player)
        old_influence = player.influence.get(faction, 0)

        # Direct adjustment for admin, bypassing soft caps
        player.influence[faction] = max(0, player.influence.get(faction, 0) + delta)
        self.state.upsert_player(player)

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline=f"Administrative Influence Adjustment",
            body=(
                f"Player {player.display_name}'s {faction} influence adjusted by {delta:+d} "
                f"(from {old_influence} to {player.influence[faction]})\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}"
            ),
            metadata={
                "admin": admin_id,
                "player": player_id,
                "faction": faction,
                "delta": delta,
                "reason": reason,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_influence_adjustment",
                payload={
                    "admin": admin_id,
                    "player": player_id,
                    "faction": faction,
                    "delta": delta,
                    "old": old_influence,
                    "new": player.influence[faction],
                    "reason": reason,
                },
            )
        )

        return press

    def admin_force_defection(
        self,
        admin_id: str,
        scholar_id: str,
        new_faction: str,
        reason: str,
    ) -> PressRelease:
        """Admin command to force a scholar defection."""
        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        old_faction = scholar.contract.get("employer", "Unknown")

        # Force the defection
        defection_triggered, press = self.evaluate_defection_offer(
            scholar_id=scholar_id,
            offer_quality=10.0,  # Maximum quality to guarantee defection
            mistreatment=0.0,
            alignment=1.0,
            plateau=0.0,
            new_faction=new_faction,
        )

        # Add admin note to the press release
        admin_press = PressRelease(
            type="admin_action",
            headline=f"Administrative Defection Order",
            body=(
                f"Scholar {scholar.name} has been ordered to defect from {old_faction} to {new_faction}\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}\n\n"
                f"Original Press:\n{press.body}"
            ),
            metadata={
                "admin": admin_id,
                "scholar": scholar_id,
                "old_faction": old_faction,
                "new_faction": new_faction,
                "reason": reason,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(admin_press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_force_defection",
                payload={
                    "admin": admin_id,
                    "scholar": scholar_id,
                    "new_faction": new_faction,
                    "reason": reason,
                },
            )
        )

        return admin_press

    def admin_cancel_expedition(
        self,
        admin_id: str,
        expedition_code: str,
        reason: str,
    ) -> PressRelease:
        """Admin command to cancel a pending expedition."""
        # Check if expedition exists in pending expeditions
        if expedition_code not in self._pending_expeditions:
            raise ValueError(f"Expedition {expedition_code} not found or already resolved")

        expedition = self._pending_expeditions[expedition_code]

        # Remove from pending expeditions
        del self._pending_expeditions[expedition_code]

        # Record cancellation in database
        self.state.record_expedition(
            ExpeditionRecord(
                code=expedition_code,
                timestamp=datetime.now(timezone.utc),
                player_id=expedition.player_id,
                expedition_type=expedition.expedition_type,
                objective=expedition.objective,
                team=expedition.team,
                funding=expedition.funding,
                prep_depth=expedition.prep_depth,
                confidence=expedition.confidence.value,
                outcome=ExpeditionOutcome.FAILURE,
                reputation_delta=0,
            ),
            result_payload={"cancelled": True, "admin": admin_id, "reason": reason},
        )

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline=f"Expedition Cancelled by Administration",
            body=(
                f"Expedition {expedition_code} has been cancelled\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}\n"
                f"No reputation changes will be applied."
            ),
            metadata={
                "admin": admin_id,
                "expedition_code": expedition_code,
                "reason": reason,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_cancel_expedition",
                payload={
                    "admin": admin_id,
                    "expedition_code": expedition_code,
                    "reason": reason,
                },
            )
        )

        return press

    def wager_reference(self) -> Dict[str, object]:
        """Expose wager tuning, thresholds, and reputation bounds for UX surfaces."""

        wagers: Dict[str, Dict[str, object]] = {}
        for level in ConfidenceLevel:
            config = self.settings.confidence_wagers.get(level.value, {})
            wagers[level.value] = {
                "reward": int(config.get("reward", 0)),
                "penalty": int(config.get("penalty", 0)),
                "triggers_recruitment_cooldown": level is ConfidenceLevel.STAKE_CAREER,
            }
        bounds = self.settings.reputation_bounds
        return {
            "wagers": wagers,
            "action_thresholds": dict(self.settings.action_thresholds),
            "reputation_bounds": {
                "min": int(bounds.get("min", 0)),
                "max": int(bounds.get("max", 0)),
            },
        }

    def export_press_archive(self, limit: int = 10, offset: int = 0) -> List[PressRecord]:
        return self.state.list_press_releases(limit=limit, offset=offset)

    def export_log(self, limit: int = 20) -> Dict[str, Iterable[object]]:
        events = self.state.export_events()
        press = self.state.list_press_releases(limit=limit)
        return {"events": events[-limit:], "press": press}

    def export_web_archive(self, output_dir: Path | None = None) -> Path:
        """Export the complete game history as a static web archive.

        Args:
            output_dir: Directory to export to. Defaults to ./web_archive

        Returns:
            Path to the exported archive directory
        """
        from pathlib import Path
        from .web_archive import WebArchive

        if output_dir is None:
            output_dir = Path("web_archive")

        archive = WebArchive(self.state, output_dir)
        return archive.export_full_archive()

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
        releases.extend(self.resolve_conferences())
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
        """Progress careers only for scholars with active mentorships."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)

        # First resolve pending mentorships
        releases.extend(self._resolve_mentorships())

        for scholar in list(self.state.all_scholars()):
            # Check if scholar has an active mentorship
            mentorship = self.state.get_active_mentorship(scholar.id)
            if not mentorship:
                continue  # No mentor, no progression

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

                # Get mentor's name for the press release
                mentor_player = self.state.get_player(mentorship[1])
                mentor_name = mentor_player.display_name if mentor_player else "their mentor"

                quote = f"Advanced to {scholar.career['tier']} under the guidance of {mentor_name}."
                press = academic_gossip(
                    GossipContext(scholar=scholar.name, quote=quote, trigger="Career advancement"),
                )
                releases.append(press)
                self._archive_press(press, now)
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="career_progression",
                        payload={
                            "scholar": scholar.id,
                            "new_tier": scholar.career["tier"],
                            "mentor": mentorship[1],
                        },
                    )
                )

                # Complete mentorship after max tier reached
                if idx == len(ladder) - 2:  # Just reached final tier
                    self.state.complete_mentorship(mentorship[0], now)
                    complete_press = academic_gossip(
                        GossipContext(
                            scholar=mentor_name,
                            quote=f"My mentorship of {scholar.name} is complete. They have reached the pinnacle of their field.",
                            trigger="Mentorship completed",
                        )
                    )
                    releases.append(complete_press)
                    self._archive_press(complete_press, now)

            self.state.save_scholar(scholar)
        return releases

    def _resolve_mentorships(self) -> List[PressRelease]:
        """Resolve pending mentorships at digest time."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)

        for mentorship_id, player_id, scholar_id, career_track in self.state.get_pending_mentorships():
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue

            player = self.state.get_player(player_id)
            if not player:
                continue

            # Check if scholar already has an active mentorship (shouldn't happen but be safe)
            existing = self.state.get_active_mentorship(scholar_id)
            if existing:
                continue

            # Activate the mentorship
            self.state.activate_mentorship(mentorship_id)

            # Update scholar's career track if specified
            if career_track and career_track in self._CAREER_TRACKS:
                old_track = scholar.career.get("track", "Academia")
                if old_track != career_track:
                    scholar.career["track"] = career_track
                    scholar.career["tier"] = self._CAREER_TRACKS[career_track][0]
                    scholar.career["ticks"] = 0
                    self.state.save_scholar(scholar)

            # Generate press release
            quote = f"The mentorship between {player.display_name} and {scholar.name} has officially commenced."
            press = academic_gossip(
                GossipContext(
                    scholar="The Academy",
                    quote=quote,
                    trigger="Mentorship activation",
                )
            )
            releases.append(press)
            self._archive_press(press, now)

            self.state.append_event(
                Event(
                    timestamp=now,
                    action="mentorship_activated",
                    payload={
                        "player": player_id,
                        "scholar": scholar_id,
                        "mentorship_id": mentorship_id,
                    },
                )
            )

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
            elif kind == "evaluate_offer":
                # Resolve offer negotiation
                offer_id = payload.get("offer_id")
                if offer_id:
                    negotiation_press = self.resolve_offer_negotiation(offer_id)
                    releases.extend(negotiation_press)
                    self.state.clear_followup(followup_id)
                    continue  # Skip the normal gossip generation
                quote = "The negotiation deadline has arrived."
            elif kind == "evaluate_counter":
                # Resolve counter-offer negotiation
                counter_offer_id = payload.get("counter_offer_id")
                if counter_offer_id:
                    negotiation_press = self.resolve_offer_negotiation(counter_offer_id)
                    releases.extend(negotiation_press)
                    self.state.clear_followup(followup_id)
                    continue  # Skip the normal gossip generation
                quote = "The counter-offer awaits final resolution."
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

    def _apply_sideways_effects(
        self, order: ExpeditionOrder, result, player: Player
    ) -> List[PressRelease]:
        """Apply mechanical effects from sideways discoveries."""
        if not result.sideways_effects:
            return []

        releases = []
        now = datetime.now(timezone.utc)

        for effect in result.sideways_effects:
            if effect.effect_type == SidewaysEffectType.FACTION_SHIFT:
                # Apply faction influence change
                faction = effect.payload["faction"]
                amount = effect.payload["amount"]
                old_influence = player.influence.get(faction, 0)
                self._apply_influence_change(player, faction, amount)
                releases.append(
                    PressRelease(
                        type="faction_shift",
                        headline=f"Expedition Discovery Shifts {faction} Relations",
                        body=f"{effect.description}. {player.name}'s {faction} influence changes by {amount} (from {old_influence} to {player.influence[faction]}).",
                        metadata={"player": player.name, "faction": faction, "change": amount},
                    )
                )

            elif effect.effect_type == SidewaysEffectType.SPAWN_THEORY:
                # Create a new theory from the discovery
                theory_text = effect.payload["theory"]
                confidence = ConfidenceLevel(effect.payload["confidence"])
                theory_record = TheoryRecord(
                    player_id=order.player_id,
                    theory=theory_text,
                    confidence=confidence.value,
                    timestamp=now,
                )
                self.state.record_theory(theory_record)
                releases.append(
                    PressRelease(
                        type="discovery_theory",
                        headline="Discovery Spawns New Theory",
                        body=f"{effect.description}. {player.name} proposes: '{theory_text}' with {confidence.value} confidence.",
                        metadata={"player": player.name, "theory": theory_text},
                    )
                )

            elif effect.effect_type == SidewaysEffectType.CREATE_GRUDGE:
                # Create a grudge between scholars
                target_id = effect.payload["target"]
                intensity = effect.payload["intensity"]

                # If target is "random", pick a random scholar
                if target_id == "random":
                    scholars = list(self.state.all_scholars())
                    # Filter out scholars on the same team as the expedition
                    eligible = [s for s in scholars if s.id not in order.team]
                    if eligible:
                        target = self._rng.choice(eligible)
                        target_id = target.id
                        # Make the target scholar dislike the player
                        target.memory.adjust_feeling(order.player_id, -intensity)
                        self.state.save_scholar(target)
                        releases.append(
                            PressRelease(
                                type="scholar_grudge",
                                headline=f"{target.name} Objects to Expedition Approach",
                                body=f"{effect.description}. {target.name} expresses concerns about {player.name}'s expedition methods.",
                                metadata={"scholar": target.name, "player": player.name},
                            )
                        )

            elif effect.effect_type == SidewaysEffectType.QUEUE_ORDER:
                # Queue a follow-up order (conference, summit, etc.)
                order_type = effect.payload["order_type"]
                order_data = effect.payload["order_data"]

                if order_type == "conference":
                    # Auto-schedule a conference by first creating a theory
                    theory_text = order_data.get("topic", "Emergency colloquium on expedition findings")
                    # Submit the theory first
                    theory_record = TheoryRecord(
                        player_id=order.player_id,
                        theory=theory_text,
                        confidence=ConfidenceLevel.SUSPECT.value,
                        timestamp=now,
                    )
                    self.state.record_theory(theory_record)
                    # Get the theory ID we just created
                    theory_id = self.state.get_last_theory_id_by_player(order.player_id)
                    # Now launch a conference on this theory
                    if theory_id:
                        # Pick some random scholars as supporters/opposition
                        scholars = list(self.state.all_scholars())[:6]
                        supporters = [s.id for s in scholars[:3]]
                        opposition = [s.id for s in scholars[3:6]]
                        self.launch_conference(
                            order.player_id,
                            theory_id,
                            ConfidenceLevel.SUSPECT,
                            supporters,
                            opposition
                        )
                        releases.append(
                            PressRelease(
                                type="conference_scheduled",
                                headline="Emergency Colloquium Scheduled",
                                body=f"{effect.description}. Conference scheduled to discuss expedition findings.",
                                metadata={"player": player.name},
                            )
                        )

            elif effect.effect_type == SidewaysEffectType.REPUTATION_CHANGE:
                # Change player reputation
                amount = effect.payload["amount"]
                old_rep = player.reputation
                player.reputation = max(
                    self.settings.reputation_bounds[0],
                    min(self.settings.reputation_bounds[1], player.reputation + amount),
                )
                releases.append(
                    PressRelease(
                        type="reputation_shift",
                        headline="Discovery Affects Academic Standing",
                        body=f"{effect.description}. {player.name}'s reputation changes by {amount} (from {old_rep} to {player.reputation}).",
                        metadata={"player": player.name, "change": amount},
                    )
                )

            elif effect.effect_type == SidewaysEffectType.UNLOCK_OPPORTUNITY:
                # Store opportunity in followups table for later resolution
                opportunity_type = effect.payload["type"]
                details = effect.payload["details"]
                deadline = now + timedelta(days=details.get("expires_in_days", 3))

                self.state.save_followup(
                    source_type="expedition_opportunity",
                    source_id=order.code,
                    scheduled_for=deadline,
                    action_type=opportunity_type,
                    action_payload=details,
                )
                releases.append(
                    PressRelease(
                        type="opportunity_unlocked",
                        headline="New Opportunity Emerges",
                        body=f"{effect.description}. Opportunity expires in {details.get('expires_in_days', 3)} days.",
                        metadata={"player": player.name, "opportunity": opportunity_type},
                    )
                )

        # Save player changes and archive press releases
        self.state.upsert_player(player)
        for release in releases:
            self._archive_press(release, now)

        return releases

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
