"""Tests for GameService theory submission and validation logic."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from great_work.models import ConfidenceLevel, Player
from great_work.service import GameService


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
        deadline="2024-12-31"
    )

    # Verify press release
    assert press.type == "academic_bulletin"
    assert "Academic Bulletin" in press.headline
    assert "lunar cycles" in press.body
    assert "certain confidence" in press.body.lower()
    assert "s.ironquill" in press.body
    assert "2024-12-31" in press.body

    # Verify event was recorded
    events = service.state.export_events()
    theory_event = next((e for e in events if e.action == "submit_theory"), None)
    assert theory_event is not None
    assert theory_event.payload["player"] == "researcher1"
    assert theory_event.payload["theory"] == "The ancient calendar aligns with lunar cycles"
    assert theory_event.payload["confidence"] == "certain"

    # Verify theory was recorded in database
    theories = service.state.pending_theories()
    assert any(t.theory == "The ancient calendar aligns with lunar cycles" for t in theories)

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

    assert "suspect confidence" in press.body.lower()
    assert "Supporting scholars: None" in press.body


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

    assert "stake_my_career confidence" in press.body.lower()

    # Verify high-stakes theory is recorded
    events = service.state.export_events()
    theory_event = next((e for e in events if e.action == "submit_theory"), None)
    assert theory_event.payload["confidence"] == "stake_career"


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
    assert player.reputation == service.settings.reputation_bounds["initial"]
    assert player.influence == {}
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

    assert "Supporting scholars: None" in press.body

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

    # All supporters should be listed
    for supporter in supporters:
        assert supporter in press.body


def test_theory_deadline_formats(tmp_path):
    """Theory submission should handle various deadline formats."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    service.ensure_player("planner")

    test_cases = [
        "2024-12-31",
        "2025-01-15",
        "December 31, 2024",
        "Jan 15, 2025"
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
        matching = [t for t in theories if deadline in t.deadline]
        assert len(matching) > 0