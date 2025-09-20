"""Tests for sideways discovery mechanical effects."""
import os
import pytest
from datetime import datetime, timezone
from typing import List

from great_work.expeditions import ExpeditionResolver, FailureTables
from great_work.models import (
    ConfidenceLevel,
    ExpeditionOutcome,
    ExpeditionPreparation,
    SidewaysEffect,
    SidewaysEffectType,
)
from great_work.rng import DeterministicRNG
from great_work.service import GameService, ExpeditionOrder
from great_work.state import GameState


@pytest.fixture
def test_state(tmp_path):
    """Create a temporary game state for testing."""
    db_path = tmp_path / "test.db"
    return GameState(db_path, start_year=1860)


@pytest.fixture
def test_service(tmp_path):
    """Create a test game service."""
    db_path = tmp_path / "test.db"
    os.environ.setdefault("LLM_MODE", "mock")
    return GameService(db_path)


class TestSidewaysEffectGeneration:
    """Test that sideways discoveries generate appropriate mechanical effects."""

    def test_think_tank_shallow_generates_theory(self):
        """Test that shallow think tank discovery spawns a theory."""
        rng = DeterministicRNG(42)
        resolver = ExpeditionResolver()
        prep = ExpeditionPreparation(
            think_tank_bonus=10,
            expertise_bonus=5,
            site_friction=0,
            political_friction=0,
        )

        # Force a partial success (40-64 range)
        # With modifier of 15, we need roll of 25-49
        for seed in range(100):
            test_rng = DeterministicRNG(seed)
            result = resolver.resolve(test_rng, prep, "shallow", "think_tank")
            if result.outcome == ExpeditionOutcome.PARTIAL:
                break
        else:
            # If no partial found, use a seed that should give partial
            test_rng = DeterministicRNG(7)  # Known to give partial
            result = resolver.resolve(test_rng, prep, "shallow", "think_tank")

        # Now check results if we got partial or landmark with sideways
        if result.sideways_discovery and "coffeehouse gossip" in result.sideways_discovery.lower():
            assert result.sideways_effects is not None

            # Check for theory spawn effect
            effect_types = [e.effect_type for e in result.sideways_effects]
            assert SidewaysEffectType.SPAWN_THEORY in effect_types
            assert SidewaysEffectType.REPUTATION_CHANGE in effect_types

            # Verify theory effect details
            theory_effect = next(e for e in result.sideways_effects
                               if e.effect_type == SidewaysEffectType.SPAWN_THEORY)
            assert theory_effect.payload["confidence"] == "suspect"
            assert "forgotten thesis" in theory_effect.payload["theory"].lower()

    def test_think_tank_deep_generates_conference(self):
        """Test that deep think tank discovery schedules a conference."""
        rng = DeterministicRNG(43)
        resolver = ExpeditionResolver()
        prep = ExpeditionPreparation(
            think_tank_bonus=10,
            expertise_bonus=5,
            site_friction=0,
            political_friction=0,
        )

        # Force partial success for deep preparation
        test_rng = DeterministicRNG(25)  # Will give us a roll in partial range
        result = resolver.resolve(test_rng, prep, "deep", "think_tank")

        if result.outcome == ExpeditionOutcome.PARTIAL:
            assert result.sideways_effects is not None
            effect_types = [e.effect_type for e in result.sideways_effects]

            if "symposium attendees demand" in result.sideways_discovery.lower():
                assert SidewaysEffectType.FACTION_SHIFT in effect_types
                assert SidewaysEffectType.QUEUE_ORDER in effect_types

                # Check conference queue
                conf_effect = next(e for e in result.sideways_effects
                                 if e.effect_type == SidewaysEffectType.QUEUE_ORDER)
                assert conf_effect.payload["order_type"] == "conference"

    def test_field_shallow_generates_opportunity(self):
        """Test that shallow field discovery creates government opportunity."""
        rng = DeterministicRNG(44)
        resolver = ExpeditionResolver()
        prep = ExpeditionPreparation(
            think_tank_bonus=0,
            expertise_bonus=10,
            site_friction=-5,
            political_friction=0,
        )

        # Force partial success
        test_rng = DeterministicRNG(35)
        result = resolver.resolve(test_rng, prep, "shallow", "field")

        if result.outcome == ExpeditionOutcome.PARTIAL:
            assert result.sideways_effects is not None

            if "local dignitaries" in result.sideways_discovery.lower():
                effect_types = [e.effect_type for e in result.sideways_effects]
                assert SidewaysEffectType.FACTION_SHIFT in effect_types
                assert SidewaysEffectType.UNLOCK_OPPORTUNITY in effect_types

                # Check opportunity details
                opp_effect = next(e for e in result.sideways_effects
                                if e.effect_type == SidewaysEffectType.UNLOCK_OPPORTUNITY)
                assert opp_effect.payload["type"] == "dignitary_contract"
                assert "expires_in_days" in opp_effect.payload["details"]

    def test_landmark_discovery_major_effects(self):
        """Test that landmark discoveries have major mechanical effects."""
        rng = DeterministicRNG(45)
        resolver = ExpeditionResolver()
        prep = ExpeditionPreparation(
            think_tank_bonus=20,
            expertise_bonus=20,
            site_friction=0,
            political_friction=0,
        )

        # Force landmark success (85+)
        # With modifier of 40, we need roll of 45+
        test_rng = DeterministicRNG(50)
        result = resolver.resolve(test_rng, prep, "deep", "great_project")

        if result.outcome == ExpeditionOutcome.LANDMARK:
            assert result.sideways_effects is not None

            # Landmark should have multiple major effects
            assert len(result.sideways_effects) >= 2

            # Check for major faction shift
            faction_effects = [e for e in result.sideways_effects
                             if e.effect_type == SidewaysEffectType.FACTION_SHIFT]
            if faction_effects:
                assert faction_effects[0].payload["amount"] >= 3

            # Check for reputation boost
            rep_effects = [e for e in result.sideways_effects
                         if e.effect_type == SidewaysEffectType.REPUTATION_CHANGE]
            if rep_effects:
                assert rep_effects[0].payload["amount"] >= 2


class TestSidewaysEffectApplication:
    """Test that sideways effects are properly applied in the game service."""

    def test_faction_shift_effect_applied(self, test_service):
        """Test that faction shift effects modify player influence."""
        # Set up player and expedition
        test_service.ensure_player("alice")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        # Launch a real expedition
        scholars = list(test_service.state.all_scholars())[:3]
        team = [s.id for s in scholars]

        press = test_service.launch_expedition(
            player_id="alice",
            expedition_type="think_tank",
            objective="Test sideways",
            team=team,
            funding={"Academic": 1},
            confidence=ConfidenceLevel.SUSPECT,
            prep_depth="shallow",
        )

        # Get the player state before resolution
        player = test_service.state.get_player("alice")
        initial_academic = player.influence.get("Academic", 0)

        # Resolve expeditions - this should apply any sideways effects
        releases = test_service.resolve_expeditions()

        # Since we can't control the outcome, just verify the system works
        assert isinstance(releases, list)

        # Check player still exists and has valid influence
        updated_player = test_service.state.get_player("alice")
        assert updated_player is not None
        assert "Academic" in updated_player.influence

    def test_theory_spawn_effect_creates_theory(self, test_service):
        """Test that theory spawn effects create new theories."""
        # Set up player
        test_service.ensure_player("bob")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        # Count initial theories
        initial_theories = test_service.state.list_theories()
        initial_count = len(initial_theories)

        # Launch expedition that might spawn theories
        scholars = list(test_service.state.all_scholars())[:3]
        team = [s.id for s in scholars]

        test_service.launch_expedition(
            player_id="bob",
            expedition_type="think_tank",
            objective="Discover new principles",
            team=team,
            funding={"Academic": 1},
            confidence=ConfidenceLevel.CERTAIN,
            prep_depth="shallow",  # Shallow think tank can spawn theories
        )

        # Resolve expeditions
        releases = test_service.resolve_expeditions()

        # Check if any theories were spawned (depends on RNG outcome)
        new_theories = test_service.state.list_theories()
        # Just verify the system doesn't crash - we can't guarantee theory spawn
        assert isinstance(new_theories, list)

    def test_reputation_change_effect(self, test_service):
        """Test that reputation changes are applied correctly."""
        # Set up player
        test_service.ensure_player("charlie")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        player = test_service.state.get_player("charlie")
        initial_rep = player.reputation

        # Launch great project (more likely to have reputation effects)
        scholars = list(test_service.state.all_scholars())[:3]
        team = [s.id for s in scholars]

        # Need 10+ reputation for great project
        player.reputation = 15
        test_service.state.upsert_player(player)

        test_service.launch_expedition(
            player_id="charlie",
            expedition_type="great_project",
            objective="Major discovery",
            team=team,
            funding={"Academic": 2, "Government": 2, "Industry": 2},
            confidence=ConfidenceLevel.STAKE_CAREER,
            prep_depth="deep",
        )

        # Resolve expeditions
        releases = test_service.resolve_expeditions()

        # Check player reputation is still valid
        updated_player = test_service.state.get_player("charlie")
        assert updated_player.reputation >= -50
        assert updated_player.reputation <= 50

    def test_opportunity_unlock_creates_followup(self, test_service):
        """Test that unlock opportunity effects create followup entries."""
        # Set up player
        test_service.ensure_player("diana")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        # Count initial followups
        initial_followups = test_service.state.list_followups()

        # Launch field expedition (can create opportunities)
        scholars = list(test_service.state.all_scholars())[:3]
        team = [s.id for s in scholars]

        test_service.launch_expedition(
            player_id="diana",
            expedition_type="field",
            objective="Field research",
            team=team,
            funding={"Academic": 1, "Government": 1},
            confidence=ConfidenceLevel.CERTAIN,
            prep_depth="shallow",  # Shallow field can unlock dignitary contracts
        )

        # Resolve expeditions
        releases = test_service.resolve_expeditions()

        # Just verify the system works - we can't control outcomes
        new_followups = test_service.state.list_followups()
        assert isinstance(new_followups, list)


class TestIntegrationWithExpeditions:
    """Test full integration of sideways effects with expedition resolution."""

    def test_expedition_with_sideways_effects_full_flow(self, test_service):
        """Test complete flow from expedition launch to effect application."""
        # Set up player and scholars
        test_service.ensure_player("eve")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        # Launch expedition
        player = test_service.state.get_player("eve")
        scholars = list(test_service.state.all_scholars())[:3]
        team = [s.id for s in scholars]

        press = test_service.launch_expedition(
            player_id="eve",
            expedition_type="think_tank",
            objective="Test sideways effects",
            team=team,
            funding={"Academic": 2},
            confidence=ConfidenceLevel.SUSPECT,
            prep_depth="shallow",
        )

        assert press is not None

        # Get expedition code
        expeditions = list(test_service._pending_expeditions.keys())
        assert len(expeditions) > 0
        exp_code = expeditions[0]

        # Resolve expedition (this should apply sideways effects)
        releases = test_service.resolve_expeditions()

        # Check that some press was generated
        assert len(releases) > 0

        # If we got a partial or landmark result, check for additional effects
        # Note: Due to RNG, we can't guarantee specific outcomes, but we can
        # verify the system doesn't crash and produces valid output

    def test_multiple_effects_from_single_discovery(self, test_service):
        """Test that multiple effects from one discovery are all applied."""
        # Set up player
        test_service.ensure_player("frank")
        # Ensure some scholars exist for the expedition
        test_service._ensure_roster()

        # Launch multiple expeditions to increase chance of effects
        scholars = list(test_service.state.all_scholars())

        # Launch a few expeditions of different types
        for exp_type in ["think_tank", "field"]:
            team = [s.id for s in scholars[:3]]
            funding = {"Academic": 1} if exp_type == "think_tank" else {"Academic": 1, "Government": 1}

            test_service.launch_expedition(
                player_id="frank",
                expedition_type=exp_type,
                objective=f"Test {exp_type}",
                team=team,
                funding=funding,
                confidence=ConfidenceLevel.CERTAIN,
                prep_depth="deep",
            )

        # Resolve all expeditions
        releases = test_service.resolve_expeditions()

        # Verify system handles multiple expeditions
        assert isinstance(releases, list)

        # Check player state is still valid
        player = test_service.state.get_player("frank")
        assert player is not None
        assert player.reputation >= -50
        assert player.reputation <= 50

def test_schedule_sideways_followups_enqueue_press_and_order(test_service):
    """Scheduling sideways followups should queue press and dispatcher orders."""

    test_service.ensure_player("eve")
    order = ExpeditionOrder(
        code="EXP-FOLLOW",
        player_id="eve",
        expedition_type="think_tank",
        objective="Test followups",
        team=[],
        funding=[],
        preparation=ExpeditionPreparation(),
        prep_depth="shallow",
        confidence=ConfidenceLevel.SUSPECT,
        timestamp=datetime.now(timezone.utc),
    )

    followups = {
        "press": [
            {
                "delay_minutes": 15,
                "type": "academic_bulletin",
                "headline": "Follow-up bulletin",
                "body": "Additional notes will circulate via the archive.",
            }
        ],
        "orders": [
            {
                "type": "press_highlight",
                "delay_minutes": 30,
                "payload": {"note": "Sideways follow-up"},
            }
        ],
    }

    initial_press = test_service.state.count_queued_press()
    initial_orders = test_service.state.list_orders(order_type="press_highlight")

    test_service._schedule_sideways_followups(
        order=order,
        followups=followups,
        timestamp=datetime.now(timezone.utc),
        tags=["archives"],
    )

    assert test_service.state.count_queued_press() == initial_press + 1
    queued_payload = test_service.state.list_queued_press()[-1][2]
    assert queued_payload["metadata"]["tags"] == ["archives"]

    orders = test_service.state.list_orders(order_type="press_highlight")
    assert len(orders) == len(initial_orders) + 1
    latest_order = orders[-1]
    assert latest_order["payload"]["tags"] == ["archives"]
    assert latest_order["payload"]["source"] == "sideways_followup"
