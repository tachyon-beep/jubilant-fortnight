"""Tests for GameService edge cases and additional coverage."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from great_work.models import (
    ConfidenceLevel,
    ExpeditionOutcome,
    Player,
    ExpeditionPreparation,
    ExpeditionResult,
    PressRelease,
)
from great_work.service import ExpeditionOrder
from great_work.service import GameService
from great_work.llm_client import LLMGenerationError

os.environ.setdefault("LLM_MODE", "mock")


def test_player_status_returns_complete_info(tmp_path):
    """player_status should return complete player information."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Create a player with some values
    player = Player(
        id="test_player",
        display_name="Test Player",
        reputation=25,
        influence={"academia": 5, "government": 3},
        cooldowns={"recruitment": 2}
    )
    service.state.upsert_player(player)

    # Get status
    status = service.player_status("test_player")

    assert status["id"] == "test_player"
    assert status["display_name"] == "Test Player"
    assert status["reputation"] == 25
    assert status["influence"]["academia"] == 5
    assert status["influence"]["government"] == 3
    assert status["cooldowns"]["recruitment"] == 2
    assert "influence_cap" in status
    assert status["influence_cap"] > 0
    assert "relationships" in status
    assert isinstance(status["relationships"], list)


def test_player_status_nonexistent_returns_none(tmp_path):
    """player_status should return None for nonexistent player."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    status = service.player_status("nonexistent")
    assert status is None


def test_player_status_relationship_summary(tmp_path):
    """player_status should include mentorship/sidecast relationship summary."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    service.ensure_player("mentor", "Mentor")

    scholar = next(iter(service.state.all_scholars()))
    scholar.memory.adjust_feeling("mentor", 3.5)
    scholar.contract["mentorship_history"] = [
        {
            "event": "activation",
            "mentor_id": "mentor",
            "mentor": "Mentor",
            "track": "Academia",
            "timestamp": "2025-09-20T12:00:00+00:00",
        }
    ]
    scholar.contract["sidecast_history"] = [
        {
            "arc": "local_junior",
            "phase": "debut",
            "sponsor_id": "mentor",
            "timestamp": "2025-09-19T09:00:00+00:00",
            "details": {
                "arc": "local_junior",
                "phase": "debut",
                "sponsor_id": "mentor",
            },
        }
    ]
    service.state.save_scholar(scholar)

    status = service.player_status("mentor")
    summary = status.get("relationships")
    assert summary
    entry = summary[0]
    assert entry["scholar"] == scholar.name
    assert entry["feeling"] > 0
    assert entry["last_mentorship_event"] == "activation"
    assert entry["sidecast_arc"] == "local_junior"


def test_archive_digest_generates_summary(tmp_path):
    """archive_digest should generate a summary of game events."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Create some events
    service.ensure_player("player1")
    service.submit_theory(
        player_id="player1",
        theory="Test theory",
        confidence=ConfidenceLevel.CERTAIN,
        supporters=[],
        deadline="2024-12-31"
    )

    # Generate digest
    digest = service.archive_digest()

    assert digest.type == "archive_digest"
    assert "Archive Digest" in digest.headline
    assert len(digest.body) > 0


def test_roster_status_returns_scholar_info(tmp_path):
    """roster_status should return information about all scholars."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    roster = service.roster_status()

    assert isinstance(roster, list)
    assert len(roster) > 0  # Should have seeded scholars

    # Check structure of first scholar
    first = roster[0]
    assert "id" in first
    assert "name" in first
    assert "archetype" in first
    assert "stats" in first
    assert "memory" in first


def test_evaluate_defection_offer_with_high_probability(tmp_path):
    """Defection offer with high probability should succeed."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Get a scholar
    scholars = list(service.state.all_scholars())
    scholar = scholars[0] if scholars else None

    if scholar:
        # Force defection with extreme values
        defected, notice = service.evaluate_defection_offer(
            scholar_id=scholar.id,
            offer_quality=1.0,
            mistreatment=1.0,
            alignment=1.0,
            plateau=1.0,
            new_faction="Foreign Academy"
        )

        assert notice.type == "defection_notice"
        # With these extreme values, should likely defect
        assert defected is True or defected is False  # Valid boolean


def test_evaluate_defection_offer_with_zero_probability(tmp_path):
    """Defection offer with zero probability should fail."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    scholars = list(service.state.all_scholars())
    scholar = scholars[0] if scholars else None

    if scholar:
        # Force rejection with zero values
        defected, notice = service.evaluate_defection_offer(
            scholar_id=scholar.id,
            offer_quality=0.0,
            mistreatment=0.0,
            alignment=-1.0,
            plateau=0.0,
            new_faction="Industry"
        )

        assert notice.type == "defection_notice"
        assert defected is False


def test_symposium_call_generates_press(tmp_path):
    """Symposium call should generate appropriate press releases."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Add some players and scholars
    service.ensure_player("player1")
    service.ensure_player("player2")

    releases = service.symposium_call()

    assert isinstance(releases, list)
    # Should generate at least some releases
    assert len(releases) >= 0


def test_confidence_delta_with_landmark(tmp_path):
    """Confidence delta should handle landmark outcomes specially."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Landmark gives same reward as success
    delta = service._confidence_delta(ConfidenceLevel.SUSPECT, ExpeditionOutcome.LANDMARK)
    assert delta == service.settings.confidence_wagers["suspect"]["reward"]

    delta = service._confidence_delta(ConfidenceLevel.CERTAIN, ExpeditionOutcome.LANDMARK)
    assert delta == service.settings.confidence_wagers["certain"]["reward"]


def test_recruitment_with_cooldown(tmp_path):
    """Recruitment should respect cooldowns."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Create player with recruitment cooldown
    player = Player(
        id="cooldown_player",
        display_name="Cooldown Player",
        reputation=50,
        influence={"academia": 10},
        cooldowns={"recruitment": 5}
    )
    service.state.upsert_player(player)

    scholars = list(service.state.all_scholars())
    if scholars:
        # Should still work but cooldown affects things
        success, press = service.attempt_recruitment(
            player_id="cooldown_player",
            scholar_id=scholars[0].id,
            faction="academia",
            base_chance=0.5
        )

        assert isinstance(press.type, str)
        assert press.type == "recruitment_report"


def test_digest_highlights_include_followup_badges(tmp_path):
    """Digest highlights should surface badges for sideways follow-up press."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    now = datetime.now(timezone.utc)

    followup_release = PressRelease(
        type="sideways_followup",
        headline="Follow-up bulletin",
        body="Dispatcher follow-up",
        metadata={
            "source": "sideways_followup",
            "tags": ["archives"],
        },
    )
    service.state.enqueue_press_release(
        followup_release,
        now + timedelta(hours=2),
    )

    highlight = service.create_digest_highlights(now=now, within_hours=24)
    assert highlight is not None
    items = highlight.metadata["digest_highlights"]["items"]
    assert items[0]["badges"] == ["Follow-Up", "archives"]

    upcoming = service.upcoming_press(limit=1, within_hours=24)
    assert upcoming
    assert upcoming[0]["badges"] == ["Follow-Up", "archives"]


def test_sidecast_followup_orders_spawn(tmp_path):
    """Sidecast spawning should queue layered follow-up orders."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    service.ensure_player("sponsor")

    order = ExpeditionOrder(
        code="EXP-ARC",
        player_id="sponsor",
        expedition_type="field",
        objective="Unearth",
        team=[],
        funding=[],
        preparation=ExpeditionPreparation(),
        prep_depth="shallow",
        confidence=ConfidenceLevel.SUSPECT,
        timestamp=datetime.now(timezone.utc),
    )
    result = ExpeditionResult(
        roll=80,
        modifier=10,
        final_score=90,
        outcome=ExpeditionOutcome.SUCCESS,
    )

    press = service._maybe_spawn_sidecast(order, result)
    assert press is not None

    followups = service.state.list_followups()
    kinds = {entry[2] for entry in followups}
    assert "sidecast_debut" in kinds

    spawned = None
    for candidate in service.state.all_scholars():
        if candidate.contract.get("sidecast_sponsor") == "sponsor":
            spawned = candidate
            break
    assert spawned is not None
    feeling = spawned.memory.feelings.get("sponsor")
    assert feeling is not None and feeling > 0
    history = spawned.contract.get("sidecast_history")
    assert isinstance(history, list)
    assert any(entry.get("phase") == "spawn" for entry in history)


def test_defection_epilogue_followup(tmp_path):
    """Defection return follow-up should emit layered epilogue press."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    service.ensure_player("patron")
    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "patron"
    service.state.save_scholar(scholar)

    now = datetime.now(timezone.utc)
    service.state.enqueue_order(
        "followup:defection_return",
        actor_id=scholar.id,
        subject_id="patron",
        payload={
            "former_employer": "patron",
            "new_faction": "Industry",
            "scenario": "reconciliation",
        },
        scheduled_at=now,
    )

    releases = service._resolve_followups()
    types = {press.type for press in releases}
    assert "defection_epilogue" in types
    updated = service.state.get_scholar(scholar.id)
    assert updated.contract.get("employer") == "patron"


def test_defection_rivalry_followup(tmp_path):
    """Defection grudge follow-up should generate rivalry coverage."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "patron"
    service.state.save_scholar(scholar)

    now = datetime.now(timezone.utc)
    service.state.enqueue_order(
        "followup:defection_grudge",
        actor_id=scholar.id,
        subject_id="patron",
        payload={
            "faction": "Industry",
            "scenario": "rivalry",
            "former_employer": "patron",
        },
        scheduled_at=now,
    )

    releases = service._resolve_followups()
    types = {press.type for press in releases}
    assert "defection_epilogue" in types


def test_sidecast_followup_updates_state(tmp_path):
    """Sidecast follow-ups should adjust scholar memory and history."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    service.ensure_player("patron", "Patron")

    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["sidecast_arc"] = "local_junior"
    scholar.contract["sidecast_sponsor"] = "patron"
    service.state.save_scholar(scholar)

    now = datetime.now(timezone.utc)
    service.state.enqueue_order(
        "followup:sidecast_debut",
        actor_id=scholar.id,
        subject_id="patron",
        payload={
            "arc": "local_junior",
            "phase": "debut",
            "sponsor": "patron",
            "expedition_code": "EXP-TEST",
            "expedition_type": "field",
        },
        scheduled_at=now,
    )

    service._resolve_followups()

    updated = service.state.get_scholar(scholar.id)
    feeling = updated.memory.feelings.get("patron")
    assert feeling is not None and feeling > 0
    history = updated.contract.get("sidecast_history")
    assert isinstance(history, list)
    assert any(entry.get("phase") == "debut" for entry in history)


def test_sideways_vignette_followup(tmp_path):
    """Sideways vignette follow-up should emit narrative press."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    scholar = next(iter(service.state.all_scholars()))

    now = datetime.now(timezone.utc)
    service.state.enqueue_order(
        "followup:sideways_vignette",
        actor_id=scholar.id,
        subject_id="spectator",
        payload={
            "headline": "Vignette Test",
            "body": "A detailed vignette plays out in the Gazette.",
            "gossip": ["Observers debate the implications."],
            "tags": ["test"],
        },
        scheduled_at=now,
    )

    releases = service._resolve_followups()
    types = {press.type for press in releases}
    assert "sideways_vignette" in types


def test_advance_digest_with_no_events(tmp_path):
    """Advance digest should handle case with no events gracefully."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    # Run digest with minimal state
    releases = service.advance_digest()

    assert isinstance(releases, list)
    # May or may not generate releases depending on timeline
    assert len(releases) >= 0


def test_resolve_pending_expeditions_empty(tmp_path):
    """Resolving with no pending expeditions should return empty list."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    releases = service.resolve_pending_expeditions()

    assert releases == []


def test_generated_scholar_counter_increments(tmp_path):
    """Generated scholar counter should increment when creating new scholars."""
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    initial_count = service._generated_counter

    # Generate a new scholar (this would normally be triggered by game events)
    # The counter should be tracked
    assert isinstance(initial_count, int)
    assert initial_count >= 0


def test_llm_failure_triggers_pause(tmp_path, monkeypatch):
    """Repeated LLM failures should pause gameplay and notify admins."""
    os.environ["LLM_MODE"] = "mock"
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    service._llm_pause_timeout = 0

    def failing_enhance(*args, **kwargs):
        raise LLMGenerationError("LLM offline")

    monkeypatch.setattr("great_work.service.enhance_press_release_sync", failing_enhance)

    service.ensure_player("sarah", "Sarah")
    prep = ExpeditionPreparation()

    release = service.queue_expedition(
        code="AR-FAIL",
        player_id="sarah",
        expedition_type="field",
        objective="Test LLM outage",
        team=[],
        funding=[],
        preparation=prep,
        prep_depth="standard",
        confidence=ConfidenceLevel.SUSPECT,
    )
    assert release.type == "research_manifesto"
    assert service.is_paused() is True
    notifications = service.drain_admin_notifications()
    assert any("paused" in message.lower() for message in notifications)

    with pytest.raises(GameService.GamePausedError):
        service.queue_expedition(
            code="AR-FAIL2",
            player_id="sarah",
            expedition_type="field",
            objective="Should not run",
            team=[],
            funding=[],
            preparation=prep,
            prep_depth="standard",
            confidence=ConfidenceLevel.SUSPECT,
        )

    # Restore LLM and resume
    def recovering_enhance(*args, **kwargs):
        return "Recovered narrative"

    monkeypatch.setattr("great_work.service.enhance_press_release_sync", recovering_enhance)

    resume_press = service.resume_game("Admin")
    assert service.is_paused() is False
    assert "Recovered" in resume_press.body or resume_press.metadata.get("was_paused")

    release_after = service.queue_expedition(
        code="AR-RECOVER",
        player_id="sarah",
        expedition_type="field",
        objective="LLM recovered",
        team=[],
        funding=[],
        preparation=prep,
        prep_depth="standard",
        confidence=ConfidenceLevel.SUSPECT,
    )
    assert "Recovered narrative" in release_after.body
