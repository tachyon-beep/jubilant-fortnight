"""Tests for GameService theory submission and validation logic."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from great_work.models import ConfidenceLevel, Player
from great_work.service import GameService

os.environ.setdefault("LLM_MODE", "mock")


def test_submit_theory_creates_bulletin(tmp_path):
    """Submitting a theory should create an academic bulletin press release."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Ensure player exists
    service.ensure_player("researcher1")

    # Submit a theory
    press = service.submit_theory(
        player_id="researcher1",
        theory="The ancient calendar aligns with lunar cycles",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=["s.ironquill", "s.scholar2"],
        deadline="2030-12-31"
    )

    # Verify press release
    assert press.type == "academic_bulletin"
    assert "Academic Bulletin" in press.headline
    assert press.body
    submission_meta = press.metadata.get("submission", {})
    assert submission_meta
    assert submission_meta["theory"] == "The ancient calendar aligns with lunar cycles"
    assert submission_meta["confidence"] == "certain"
    assert submission_meta["supporters"] == ["s.ironquill", "s.scholar2"]
    assert submission_meta["deadline"] == "2030-12-31"
    llm_meta = press.metadata.get("llm", {})
    assert llm_meta
    assert llm_meta.get("persona") == "researcher1"

    # Verify event was recorded
    events = service.state.export_events()
    theory_event = next((e for e in events if e.action == "submit_theory"), None)
    assert theory_event is not None
    assert theory_event.payload["player"] == "researcher1"
    assert theory_event.payload["theory"] == "The ancient calendar aligns with lunar cycles"
    assert theory_event.payload["confidence"] == "certain"

    # Verify theory was recorded in database
    theories = service.state.pending_theories()
    assert any(record.theory == "The ancient calendar aligns with lunar cycles" for theory_id, record in theories)

    # Verify press was archived
    archived = service.state.list_press_releases()
    assert any(item.release.type == "academic_bulletin" for item in archived)


def test_submit_theory_with_suspect_confidence(tmp_path):
    """Theory submission with SUSPECT confidence should be reflected in bulletin."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("skeptic")

    press = service.submit_theory(
        player_id="skeptic",
        theory="Preliminary hypothesis about tidal patterns",
        confidence=ConfidenceLevel.SUSPECT,
        supporters=[],
        deadline="2024-11-30"
    )

    submission_meta = press.metadata.get("submission", {})
    assert submission_meta
    assert submission_meta["confidence"] == "suspect"
    assert submission_meta["supporters"] == []


def test_submit_theory_with_career_stake(tmp_path):
    """Theory submission with STAKE_CAREER confidence should be properly recorded."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("confident_researcher")

    press = service.submit_theory(
        player_id="confident_researcher",
        theory="Revolutionary unified field theory",
        confidence=ConfidenceLevel.STAKE_CAREER,
        supporters=["s.scholar1", "s.scholar2", "s.scholar3"],
        deadline="2025-01-15"
    )

    submission_meta = press.metadata.get("submission", {})
    assert submission_meta
    assert submission_meta["confidence"] == "stake_my_career"

    # Verify high-stakes theory is recorded
    events = service.state.export_events()
    theory_event = next((e for e in events if e.action == "submit_theory"), None)
    assert theory_event.payload["confidence"] == "stake_my_career"


def test_submit_multiple_theories_increments_bulletin_number(tmp_path):
    """Each theory submission should increment the bulletin number."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("prolific")

    # Submit first theory
    press1 = service.submit_theory(
        player_id="prolific",
        theory="First theory",
        confidence=ConfidenceLevel.SUSPECT,
        supporters=[],
        deadline="2024-12-01"
    )

    # Submit second theory
    press2 = service.submit_theory(
        player_id="prolific",
        theory="Second theory",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=["s.supporter"],
        deadline="2024-12-02"
    )

    # Extract bulletin numbers from headlines
    # Format: "Academic Bulletin No. X"
    num1 = int(press1.headline.split("No. ")[1])
    num2 = int(press2.headline.split("No. ")[1])

    assert num2 > num1


def test_theory_reference_snapshot_includes_status_and_supporters(tmp_path):
    """The theory reference snapshot should classify deadlines and surface supporters."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    future_deadline = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    past_deadline = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    service.ensure_player("innovator", "Innovator")
    service.ensure_player("historian", "Historian")

    service.submit_theory(
        player_id="innovator",
        theory="Ley lines intersect at the university clocktower",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=["s.lyra"],
        deadline=future_deadline,
    )
    future_id = service.state.get_last_theory_id_by_player("innovator")

    service.submit_theory(
        player_id="historian",
        theory="Ancient tide tables predict symposium attendance",
        confidence=ConfidenceLevel.SUSPECT,
        supporters=[],
        deadline=past_deadline,
    )
    past_id = service.state.get_last_theory_id_by_player("historian")

    snapshot = service.theory_reference(limit=5)

    assert snapshot["active"] >= 1
    assert snapshot["expired"] >= 1

    theories_by_id = {entry["id"]: entry for entry in snapshot["theories"]}
    future_entry = theories_by_id[future_id]
    past_entry = theories_by_id[past_id]

    assert future_entry["status"] == "active"
    assert future_entry["confidence_display"] == "Certain"
    assert future_entry["supporters"] == ["s.lyra"]
    assert future_entry["player_display"] == "Innovator"
    assert future_entry["days_remaining"] is not None and future_entry["days_remaining"] >= 0

    assert past_entry["status"] == "expired"
    assert past_entry["confidence_display"] == "Suspect"
    assert past_entry["deadline_display"] == past_deadline


def test_ensure_player_creates_new_player(tmp_path):
    """ensure_player should create a new player if not exists."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Player shouldn't exist initially
    player = service.state.get_player("new_player")
    assert player is None

    # Ensure player creates them
    service.ensure_player("new_player")

    # Player should now exist with default values
    player = service.state.get_player("new_player")
    assert player is not None
    assert player.id == "new_player"
    assert player.display_name == "new_player"
    assert player.reputation == 0  # Default initial reputation
    # Influence should be initialized with all factions at 0
    expected_influence = {"academia": 0, "government": 0, "industry": 0, "religion": 0, "foreign": 0}
    assert player.influence == expected_influence
    assert player.cooldowns == {}


def test_ensure_player_preserves_existing(tmp_path):
    """ensure_player should not modify existing player."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Create player with custom values
    player = Player(
        id="existing",
        display_name="Existing Player",
        reputation=50,
        influence={"academia": 10},
        cooldowns={"recruitment": 3}
    )
    service.state.upsert_player(player)

    # Ensure player should not modify
    service.ensure_player("existing")

    # Verify values unchanged
    retrieved = service.state.get_player("existing")
    assert retrieved.reputation == 50
    assert retrieved.influence["academia"] == 10
    assert retrieved.cooldowns["recruitment"] == 3


def test_theory_submission_with_empty_supporters(tmp_path):
    """Theory submission should handle empty supporter list gracefully."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("loner")

    press = service.submit_theory(
        player_id="loner",
        theory="Solo research on particle physics",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=[],
        deadline="2024-12-25"
    )

    submission_meta = press.metadata.get("submission", {})
    assert submission_meta
    assert submission_meta["supporters"] == []

    # Verify in event log
    events = service.state.export_events()
    theory_event = next((e for e in events if e.action == "submit_theory"), None)
    assert theory_event.payload["supporters"] == []


def test_theory_submission_with_many_supporters(tmp_path):
    """Theory submission should handle multiple supporters correctly."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("popular")

    supporters = [f"s.scholar{i}" for i in range(10)]

    press = service.submit_theory(
        player_id="popular",
        theory="Widely supported climate model",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=supporters,
        deadline="2025-01-01"
    )

    submission_meta = press.metadata.get("submission", {})
    assert submission_meta
    assert submission_meta["supporters"] == supporters


def test_theory_deadline_formats(tmp_path):
    """Theory submission should handle various deadline formats."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("planner")

    test_cases = [
        "2030-12-31",
        "2031-01-15",
        "December 31, 2030",
        "Jan 15, 2031"
    ]

    for deadline in test_cases:
        press = service.submit_theory(
            player_id="planner",
            theory=f"Theory with deadline {deadline}",
            confidence=ConfidenceLevel.SUSPECT,
            supporters=[],
            deadline=deadline
        )

        assert deadline in press.body

        # Verify stored correctly
        theories = service.state.pending_theories()
        matching = [t for t in theories if deadline in t[1].deadline]
        assert len(matching) > 0
