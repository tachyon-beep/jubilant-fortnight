"""Additional tests to improve overall coverage to ~80%."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from great_work.expeditions import ExpeditionOutcome, ExpeditionResult
from great_work.models import (
    ConfidenceLevel,
    Event,
    ExpeditionPreparation,
    ExpeditionRecord,
    Memory,
    MemoryFact,
    Player,
    PressRecord,
    PressRelease,
    Scholar,
    ScholarStats,
    TheoryRecord,
)
from great_work.press import (
    DefectionContext,
    GossipContext,
    RecruitmentContext,
    academic_gossip,
    defection_notice,
    recruitment_report,
)
from great_work.rng import DeterministicRNG, SeedSequence
from great_work.scholars import ScholarRepository
from great_work.service import GameService
from great_work.state import GameState


# Models coverage
def test_memory_decay_feelings():
    """Memory should decay feelings over time."""
    memory = Memory()
    memory.feelings["rival"] = 0.5
    memory.feelings["friend"] = 0.8
    memory.feelings["scarred"] = 0.9
    memory.scars.append("scarred")  # This one shouldn't decay

    memory.decay_feelings()

    # Regular feelings should decay
    assert memory.feelings["rival"] < 0.5
    assert memory.feelings["friend"] < 0.8
    # Scarred feelings shouldn't decay
    assert "scarred" not in memory.feelings or memory.feelings["scarred"] == 0.9


def test_memory_fact_creation():
    """MemoryFact should be created with proper attributes."""
    now = datetime.now(timezone.utc)
    fact = MemoryFact(
        timestamp=now,
        event_type="expedition_success",
        details={"outcome": "success", "reputation": 5}
    )

    assert fact.timestamp == now
    assert fact.event_type == "expedition_success"
    assert fact.details["outcome"] == "success"


def test_scholar_stats_creation():
    """ScholarStats should hold all stat values."""
    stats = ScholarStats(
        talent=80,
        reliability=75,
        integrity=90,
        theatrics=60,
        loyalty=85,
        risk=40
    )

    assert stats.talent == 80
    assert stats.reliability == 75
    assert stats.integrity == 90
    assert stats.theatrics == 60
    assert stats.loyalty == 85
    assert stats.risk == 40


def test_expedition_preparation_dataclass():
    """ExpeditionPreparation should work as a dataclass."""
    prep = ExpeditionPreparation()
    assert isinstance(prep, ExpeditionPreparation)


def test_confidence_level_enum_values():
    """ConfidenceLevel enum should have correct string values."""
    assert ConfidenceLevel.SUSPECT.value == "suspect"
    assert ConfidenceLevel.CERTAIN.value == "certain"
    assert ConfidenceLevel.STAKE_CAREER.value == "stake_career"


def test_expedition_outcome_enum_values():
    """ExpeditionOutcome enum should have correct string values."""
    assert ExpeditionOutcome.SUCCESS.value == "success"
    assert ExpeditionOutcome.PARTIAL.value == "partial"
    assert ExpeditionOutcome.FAILURE.value == "failure"
    assert ExpeditionOutcome.LANDMARK.value == "landmark"


def test_expedition_result_with_sideways_discovery():
    """ExpeditionResult should handle sideways discovery."""
    result = ExpeditionResult(
        outcome=ExpeditionOutcome.PARTIAL,
        roll=60,
        modifier=5,
        final_score=65,
        failure_detail=None,
        sideways_discovery="Unexpected fossil found"
    )

    assert result.sideways_discovery == "Unexpected fossil found"
    assert result.outcome == ExpeditionOutcome.PARTIAL


def test_press_release_with_metadata():
    """PressRelease should support metadata field."""
    release = PressRelease(
        type="special_announcement",
        headline="Breaking News",
        body="Important discovery made",
        metadata={"importance": "high", "verified": True}
    )

    assert release.metadata["importance"] == "high"
    assert release.metadata["verified"] is True


def test_event_model_serialization():
    """Event should serialize payload correctly."""
    event = Event(
        timestamp=datetime.now(timezone.utc),
        action="test_action",
        payload={"nested": {"data": [1, 2, 3]}, "flag": True}
    )

    assert event.payload["nested"]["data"] == [1, 2, 3]
    assert event.payload["flag"] is True


# Press templates additional coverage
def test_gossip_context_with_long_quote():
    """GossipContext should handle long quotes."""
    ctx = GossipContext(
        scholar="Prof. Verbose",
        quote="This is a very long quote that goes on and on about various academic matters " * 5,
        trigger="conference presentation"
    )

    press = academic_gossip(ctx)
    assert "Prof. Verbose" in press.headline
    assert len(press.body) > 100


def test_recruitment_context_low_chance():
    """RecruitmentContext with very low chance."""
    ctx = RecruitmentContext(
        player="Unlucky",
        scholar="Dr. Elusive",
        outcome="FAILURE",
        chance=0.01,
        faction="foreign"
    )

    press = recruitment_report(ctx)
    assert "1%" in press.body
    assert "FAILURE" in press.body


def test_defection_context_high_probability():
    """DefectionContext with very high probability."""
    ctx = DefectionContext(
        scholar="Dr. Opportunist",
        outcome="accepted",
        new_faction="Wealthy Patron",
        probability=0.99
    )

    press = defection_notice(ctx)
    assert "99%" in press.body
    assert "accepted" in press.body


# RNG additional tests
def test_deterministic_rng_multiple_operations():
    """DeterministicRNG should handle multiple operations in sequence."""
    rng = DeterministicRNG(seed=999)

    # Mix of different operations
    int_val = rng.randint(1, 10)
    float_val = rng.uniform(0, 1)
    choice_val = rng.choice(["a", "b", "c"])
    range_val = rng.randrange(10, 20, 2)

    # Should all be deterministic
    rng2 = DeterministicRNG(seed=999)
    assert rng2.randint(1, 10) == int_val
    assert rng2.uniform(0, 1) == float_val
    assert rng2.choice(["a", "b", "c"]) == choice_val
    assert rng2.randrange(10, 20, 2) == range_val


def test_seed_sequence_spawn_chain():
    """SeedSequence should support chained spawning."""
    root = SeedSequence(campaign_seed=5000)

    child1 = root.spawn()
    child2 = root.spawn()

    # Children should have different seeds
    assert child1.campaign_seed != child2.campaign_seed

    # Grandchildren
    grandchild1 = child1.spawn(0)
    grandchild2 = child2.spawn(0)

    assert grandchild1.campaign_seed != grandchild2.campaign_seed


# State additional coverage
def test_gamestate_with_custom_repository(tmp_path):
    """GameState should accept custom ScholarRepository."""
    custom_repo = ScholarRepository(seed=99999)
    state = GameState(
        db_path=tmp_path / "custom.db",
        repository=custom_repo,
        start_year=1920
    )

    assert state._repo.seed == 99999


def test_gamestate_update_relationship(tmp_path):
    """GameState should update scholar relationships."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Create two scholars
    repo = ScholarRepository()
    scholar1 = repo.generate("s1", "Scholar One")
    scholar2 = repo.generate("s2", "Scholar Two")

    state.save_scholar(scholar1)
    state.save_scholar(scholar2)

    # Update relationship
    state.update_relationship("s1", "s2", 0.7)

    # Retrieve relationship
    feeling = state.get_relationship("s1", "s2")
    assert feeling == 0.7


def test_gamestate_clear_followup(tmp_path):
    """GameState should clear followups correctly."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Schedule a followup
    state.schedule_followup(
        "test_scholar",
        "test_type",
        datetime.now(timezone.utc),
        {"data": "test"}
    )

    # Get the followup
    due = state.due_followups(datetime.now(timezone.utc))
    if due:
        followup_id = due[0][0]

        # Clear it
        state.clear_followup(followup_id)

        # Should be gone
        due_after = state.due_followups(datetime.now(timezone.utc))
        assert len(due_after) < len(due)


def test_press_record_model():
    """PressRecord should store press releases with timestamps."""
    record = PressRecord(
        timestamp=datetime.now(timezone.utc),
        release=PressRelease(
            type="test",
            headline="Test Headline",
            body="Test body"
        )
    )

    assert record.release.headline == "Test Headline"
    assert isinstance(record.timestamp, datetime)


def test_theory_record_model():
    """TheoryRecord should store theory submissions."""
    record = TheoryRecord(
        timestamp=datetime.now(timezone.utc),
        player_id="theorist",
        theory="Grand unified theory",
        confidence="certain",
        supporters=["s1", "s2"],
        deadline="2025-01-01"
    )

    assert record.theory == "Grand unified theory"
    assert len(record.supporters) == 2


def test_expedition_record_model():
    """ExpeditionRecord should store expedition details."""
    record = ExpeditionRecord(
        timestamp=datetime.now(timezone.utc),
        code="EXP-123",
        player_id="explorer",
        expedition_type="field",
        objective="Find artifacts",
        team=["s1", "s2", "s3"],
        funding=["academia", "government"],
        preparation={"equipment": True},
        prep_depth="deep",
        confidence="certain"
    )

    assert record.code == "EXP-123"
    assert len(record.team) == 3
    assert record.preparation["equipment"] is True