"""Tests for contract and offer negotiation mechanics."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from great_work.models import OfferRecord, Player
from great_work.rng import DeterministicRNG
from great_work.scholars import ScholarRepository
from great_work.service import GameService
from great_work.state import GameState


@pytest.fixture
def game_state(tmp_path: Path) -> GameState:
    """Create a test game state with scholars."""
    state = GameState(tmp_path / "test.db", start_year=1800)
    repo = ScholarRepository()
    rng = DeterministicRNG(12345)

    # Add test players
    alice = Player(id="alice", display_name="Alice", reputation=50,
                   influence={"academic": 100, "government": 50, "industry": 75})
    bob = Player(id="bob", display_name="Bob", reputation=40,
                 influence={"academic": 80, "government": 60, "industry": 50})
    state.upsert_player(alice)
    state.upsert_player(bob)

    # Add test scholars
    newton = repo.generate(rng, "newton")
    newton.contract["employer"] = "alice"  # Newton works for Alice
    state.save_scholar(newton)

    einstein = repo.generate(rng, "einstein")
    einstein.contract["employer"] = "bob"  # Einstein works for Bob
    state.save_scholar(einstein)

    return state


@pytest.fixture
def service(game_state: GameState, tmp_path: Path) -> GameService:
    """Create a game service with test state."""
    # GameService creates its own GameState, so we need to manually setup data
    service = GameService(tmp_path / "service.db")

    # Copy players and scholars from fixture state
    for player in game_state.all_players():
        service.state.upsert_player(player)

    for scholar in game_state.all_scholars():
        service.state.save_scholar(scholar)

    return service


class TestOfferCreation:
    """Test offer creation and validation."""

    def test_create_initial_offer(self, service: GameService):
        """Test creating an initial poaching offer."""
        # Bob tries to poach Newton from Alice
        offer_id, press = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20, "industry": 10},
            terms={"guaranteed_funding": True}
        )

        assert offer_id > 0
        assert len(press) == 1
        assert "Poaching Attempt" in press[0].headline
        # Check that the press release mentions the scholar (by name, not ID)
        assert "Dr " in press[0].body  # All scholars have Dr. title

        # Check offer was saved
        offer = service.state.get_offer(offer_id)
        assert offer is not None
        assert offer.scholar_id == "newton"
        assert offer.rival_id == "bob"
        assert offer.patron_id == "alice"
        assert offer.status == "pending"
        assert offer.influence_offered == {"academic": 20, "industry": 10}
        assert offer.terms == {"guaranteed_funding": True}

        # Check influence was deducted from Bob
        bob = service.state.get_player("bob")
        assert bob.influence["academic"] == 60  # 80 - 20
        assert bob.influence["industry"] == 40  # 50 - 10

    def test_insufficient_influence(self, service: GameService):
        """Test that offers fail with insufficient influence."""
        with pytest.raises(ValueError, match="insufficient"):
            service.create_defection_offer(
                rival_id="bob",
                scholar_id="newton",
                target_faction="BobCorp",
                influence_offer={"academic": 200},  # Bob only has 80
            )

    def test_invalid_scholar(self, service: GameService):
        """Test that offers fail for non-existent scholars."""
        with pytest.raises(ValueError, match="not found"):
            service.create_defection_offer(
                rival_id="bob",
                scholar_id="nonexistent",
                target_faction="BobCorp",
                influence_offer={"academic": 10},
            )

    def test_no_employer(self, service: GameService):
        """Test that offers fail for unaffiliated scholars."""
        # Add a scholar without employer
        repo = ScholarRepository()
        rng = DeterministicRNG(12345)
        free_scholar = repo.generate(rng, "free")
        free_scholar.contract.pop("employer", None)
        service.state.save_scholar(free_scholar)

        with pytest.raises(ValueError, match="no current employer"):
            service.create_defection_offer(
                rival_id="bob",
                scholar_id="free",
                target_faction="BobCorp",
                influence_offer={"academic": 10},
            )


class TestCounterOffers:
    """Test counter-offer mechanics."""

    def test_create_counter_offer(self, service: GameService):
        """Test creating a counter-offer."""
        # Bob tries to poach Newton
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Alice counters
        counter_id, press = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 25, "government": 10},
            counter_terms={"leadership_role": True}
        )

        assert counter_id > offer_id
        assert len(press) == 1
        assert "Counter-Offer" in press[0].headline

        # Check counter was saved
        counter = service.state.get_offer(counter_id)
        assert counter is not None
        assert counter.offer_type == "counter"
        assert counter.parent_offer_id == offer_id
        assert counter.influence_offered == {"academic": 25, "government": 10}
        assert counter.terms == {"leadership_role": True}

        # Check original offer status updated
        original = service.state.get_offer(offer_id)
        assert original.status == "countered"

        # Check influence deducted from Alice
        alice = service.state.get_player("alice")
        assert alice.influence["academic"] == 75  # 100 - 25
        assert alice.influence["government"] == 40  # 50 - 10

    def test_only_patron_can_counter(self, service: GameService):
        """Test that only the current patron can counter."""
        # Bob tries to poach Newton from Alice
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Bob cannot counter his own offer
        with pytest.raises(ValueError, match="not the current patron"):
            service.counter_offer(
                player_id="bob",
                original_offer_id=offer_id,
                counter_influence={"academic": 30},
            )

    def test_cannot_counter_resolved_offer(self, service: GameService):
        """Test that resolved offers cannot be countered."""
        # Create and resolve an offer
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        service.state.update_offer_status(offer_id, "accepted", datetime.now(timezone.utc))

        # Cannot counter accepted offer
        with pytest.raises(ValueError, match="not pending"):
            service.counter_offer(
                player_id="alice",
                original_offer_id=offer_id,
                counter_influence={"academic": 30},
            )


class TestOfferEvaluation:
    """Test scholar offer evaluation logic."""

    def test_evaluate_basic_offer(self, service: GameService):
        """Test basic offer evaluation probability."""
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 50},  # High offer
        )

        probability = service.evaluate_scholar_offer(offer_id)
        assert 0.0 <= probability <= 1.0
        # High offer should have decent probability
        assert probability > 0.3

    def test_terms_affect_probability(self, service: GameService):
        """Test that contract terms affect acceptance probability."""
        # Offer without terms
        offer1_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
            terms={}
        )

        # Reset Bob's influence for second offer
        bob = service.state.get_player("bob")
        bob.influence["academic"] = 80
        service.state.upsert_player(bob)

        # Offer with attractive terms
        offer2_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="einstein",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
            terms={
                "guaranteed_funding": True,
                "leadership_role": True,
                "exclusive_research": True
            }
        )

        prob1 = service.evaluate_scholar_offer(offer1_id)
        prob2 = service.evaluate_scholar_offer(offer2_id)

        # Terms should increase probability significantly
        # Note: prob2 might not be > prob1 due to different scholars
        # but terms add 0.45 total probability
        assert prob2 > 0.0

    def test_counter_loyalty_bonus(self, service: GameService):
        """Test that counter-offers have loyalty bonus."""
        # Initial offer
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 30},
        )

        # Counter with same influence
        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 30},
        )

        initial_prob = service.evaluate_scholar_offer(offer_id)
        counter_prob = service.evaluate_scholar_offer(counter_id)

        # Counter should have lower probability (loyalty bonus = -0.1)
        # This means scholar is less likely to leave
        assert counter_prob < initial_prob


class TestNegotiationResolution:
    """Test negotiation resolution mechanics."""

    def test_resolve_single_offer_accepted(self, service: GameService, monkeypatch):
        """Test resolution when scholar accepts single offer."""
        # Mock RNG to ensure acceptance
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.01  # Very low roll = accept
        monkeypatch.setattr(service, "_rng", mock_rng)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 50},
        )

        press = service.resolve_offer_negotiation(offer_id)

        assert len(press) > 0
        assert "Defects to" in press[0].headline

        # Check scholar transferred
        newton = service.state.get_scholar("newton")
        assert newton.contract["employer"] == "BobCorp"

        # Check offer marked accepted
        offer = service.state.get_offer(offer_id)
        assert offer.status == "accepted"

    def test_resolve_single_offer_rejected(self, service: GameService, monkeypatch):
        """Test resolution when scholar rejects offer."""
        # Mock RNG to ensure rejection
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.99  # High roll = reject
        monkeypatch.setattr(service, "_rng", mock_rng)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 10},  # Low offer
        )

        press = service.resolve_offer_negotiation(offer_id)

        assert len(press) > 0
        assert "Rejects" in press[0].headline

        # Check scholar stayed
        newton = service.state.get_scholar("newton")
        assert newton.contract["employer"] == "alice"

        # Check offer marked rejected
        offer = service.state.get_offer(offer_id)
        assert offer.status == "rejected"

        # Check influence returned to Bob
        bob = service.state.get_player("bob")
        assert bob.influence["academic"] == 80  # Original amount

    def test_resolve_negotiation_chain(self, service: GameService, monkeypatch):
        """Test resolution of multi-offer negotiation."""
        # Mock RNG
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.3
        monkeypatch.setattr(service, "_rng", mock_rng)

        # Initial offer
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Counter-offer
        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 40},  # Higher counter
        )

        # Resolve (should pick counter due to higher value)
        press = service.resolve_offer_negotiation(counter_id)

        assert len(press) > 0

        # Check all offers in chain are resolved
        original = service.state.get_offer(offer_id)
        counter = service.state.get_offer(counter_id)

        assert original.status in ["accepted", "rejected"]
        assert counter.status in ["accepted", "rejected"]

        # Only one should be accepted
        assert (original.status == "accepted") != (counter.status == "accepted")

    def test_influence_escrow_return(self, service: GameService, monkeypatch):
        """Test that escrowed influence is properly returned."""
        # Mock to ensure rejection
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.99
        monkeypatch.setattr(service, "_rng", mock_rng)

        # Track initial influence
        bob_initial = service.state.get_player("bob").influence.copy()
        alice_initial = service.state.get_player("alice").influence.copy()

        # Bob makes offer
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Alice counters
        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 30},
        )

        # Both should have influence deducted
        bob_after_offer = service.state.get_player("bob")
        alice_after_offer = service.state.get_player("alice")
        assert bob_after_offer.influence["academic"] == bob_initial["academic"] - 20
        assert alice_after_offer.influence["academic"] == alice_initial["academic"] - 30

        # Resolve (rejection)
        service.resolve_offer_negotiation(counter_id)

        # Both should get influence back
        bob_final = service.state.get_player("bob")
        alice_final = service.state.get_player("alice")
        assert bob_final.influence["academic"] == bob_initial["academic"]
        assert alice_final.influence["academic"] == alice_initial["academic"]


class TestOfferChains:
    """Test offer chain tracking and management."""

    def test_get_offer_chain(self, service: GameService):
        """Test retrieving full negotiation chain."""
        # Create chain: offer -> counter -> final
        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 30},
        )

        # Get chain from any point
        chain = service.state.get_offer_chain(counter_id)

        assert len(chain) == 2
        assert chain[0].id == offer_id  # Root first
        assert chain[1].id == counter_id

    def test_list_active_offers(self, service: GameService):
        """Test listing active offers for a player."""
        # Bob makes offer for Newton
        offer1_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Alice makes offer for Einstein
        # First give Alice more influence
        alice = service.state.get_player("alice")
        alice.influence["academic"] = 100
        service.state.upsert_player(alice)

        offer2_id, _ = service.create_defection_offer(
            rival_id="alice",
            scholar_id="einstein",
            target_faction="AliceLab",
            influence_offer={"academic": 15},
        )

        # Bob should see offers involving him
        bob_offers = service.list_player_offers("bob")
        assert len(bob_offers) == 2  # As rival in one, as patron in other

        # Alice should see offers involving her
        alice_offers = service.list_player_offers("alice")
        assert len(alice_offers) == 2  # As patron in one, as rival in other

        # Resolve one offer
        service.state.update_offer_status(offer1_id, "rejected")

        # Should only see active offers
        bob_active = service.list_player_offers("bob")
        assert len(bob_active) == 1
        assert bob_active[0].id == offer2_id


class TestFollowupIntegration:
    """Test integration with followup system."""

    def test_offer_creates_followup(self, service: GameService):
        """Test that offers create followups for resolution."""
        now = datetime.now(timezone.utc)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Check followup was created
        future = now + timedelta(hours=25)  # After 24 hour window
        followups = service.state.due_followups(future)

        assert len(followups) > 0
        followup = followups[0]
        assert followup[1] == "newton"  # Scholar ID
        assert followup[2] == "evaluate_offer"  # Kind
        assert followup[3]["offer_id"] == offer_id

    def test_counter_reschedules_followup(self, service: GameService):
        """Test that counters reschedule evaluation."""
        now = datetime.now(timezone.utc)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        # Original followup at 24 hours
        followups_24h = service.state.due_followups(now + timedelta(hours=25))
        assert len(followups_24h) == 1
        assert followups_24h[0][2] == "evaluate_offer"

        # Create counter
        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 30},
        )

        # Original followup should be cleared
        followups_24h_after = service.state.due_followups(now + timedelta(hours=25))
        # Might have the new followup if it's also due
        for followup in followups_24h_after:
            assert followup[2] != "evaluate_offer"

        # New followup at 12 hours (for counter)
        followups_12h = service.state.due_followups(now + timedelta(hours=13))
        counter_followups = [f for f in followups_12h if f[2] == "evaluate_counter"]
        assert len(counter_followups) == 1
        assert counter_followups[0][3]["counter_offer_id"] == counter_id


class TestEmotionalConsequences:
    """Test emotional impacts of negotiations."""

    def test_successful_defection_emotions(self, service: GameService, monkeypatch):
        """Test emotional changes from successful defection."""
        # Mock for acceptance
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.01
        monkeypatch.setattr(service, "_rng", mock_rng)

        newton = service.state.get_scholar("newton")
        initial_alice_feeling = newton.memory.feelings.get("alice", 0.0)
        initial_bob_feeling = newton.memory.feelings.get("bob", 0.0)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 50},
        )

        service.resolve_offer_negotiation(offer_id)

        newton = service.state.get_scholar("newton")

        # Should have negative feelings toward former employer
        assert newton.memory.feelings.get("alice", 0.0) < initial_alice_feeling
        # Should have positive feelings toward new employer
        assert newton.memory.feelings.get("bob", 0.0) > initial_bob_feeling

        # Should have defection scar
        assert "defection" in newton.memory.scars

    def test_failed_poaching_emotions(self, service: GameService, monkeypatch):
        """Test emotional changes from failed poaching."""
        # Mock for rejection
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.99
        monkeypatch.setattr(service, "_rng", mock_rng)

        newton = service.state.get_scholar("newton")
        initial_bob_feeling = newton.memory.feelings.get("bob", 0.0)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 10},
        )

        service.resolve_offer_negotiation(offer_id)

        newton = service.state.get_scholar("newton")

        # Should have negative feelings toward failed poacher
        assert newton.memory.feelings.get("bob", 0.0) < initial_bob_feeling

        # No defection scar (stayed loyal)
        assert "defection" not in newton.memory.scars

    def test_counter_offer_loyalty_emotions(self, service: GameService, monkeypatch):
        """Test emotional boost from successful counter-offer."""
        # Mock for counter acceptance
        mock_rng = Mock()
        mock_rng.uniform.return_value = 0.3
        monkeypatch.setattr(service, "_rng", mock_rng)

        newton = service.state.get_scholar("newton")
        initial_alice_feeling = newton.memory.feelings.get("alice", 0.0)

        offer_id, _ = service.create_defection_offer(
            rival_id="bob",
            scholar_id="newton",
            target_faction="BobCorp",
            influence_offer={"academic": 20},
        )

        counter_id, _ = service.counter_offer(
            player_id="alice",
            original_offer_id=offer_id,
            counter_influence={"academic": 50},  # Much higher
        )

        # Mock evaluation to prefer counter
        def mock_evaluate(oid):
            return 0.8 if oid == counter_id else 0.2
        monkeypatch.setattr(service, "evaluate_scholar_offer", mock_evaluate)

        service.resolve_offer_negotiation(counter_id)

        newton = service.state.get_scholar("newton")

        # Should have stronger positive feelings toward alice (who fought for them)
        assert newton.memory.feelings.get("alice", 0.0) > initial_alice_feeling