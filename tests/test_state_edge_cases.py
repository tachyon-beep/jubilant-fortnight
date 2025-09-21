"""Tests for GameState edge cases and error handling."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from great_work.models import (
    Event,
    ExpeditionRecord,
    Player,
    Scholar,
    TheoryRecord,
)
from great_work.rng import DeterministicRNG
from great_work.scholars import ScholarRepository
from great_work.state import GameState


def test_gamestate_init_creates_database_structure(tmp_path):
    """GameState initialization should create all required tables."""
    db_path = tmp_path / "test.db"
    GameState(db_path=db_path, start_year=1923)

    # Verify database structure
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "players", "scholars", "relationships", "theories",
        "expeditions", "events", "press_releases", "timeline", "followups", "offers"
    }
    assert expected_tables.issubset(tables)


def test_player_not_found_returns_none(tmp_path):
    """Getting a non-existent player should return None."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)
    player = state.get_player("nonexistent")
    assert player is None


def test_player_cache_invalidation(tmp_path):
    """Player cache should be invalidated when database is updated directly."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Create a player
    player = Player(
        id="test_player",
        display_name="Test Player",
        reputation=10,
        influence={"academia": 5},
        cooldowns={}
    )
    state.upsert_player(player)

    # Get player to populate cache
    cached_player = state.get_player("test_player")
    assert cached_player.reputation == 10

    # Bypass cache and update database directly
    with sqlite3.connect(state._db_path) as conn:
        conn.execute(
            "UPDATE players SET reputation = ? WHERE id = ?",
            (20, "test_player")
        )
        conn.commit()

    # Clear cache and re-fetch
    state._cached_players.clear()
    updated_player = state.get_player("test_player")
    assert updated_player.reputation == 20


def test_scholar_removal_cascades(tmp_path):
    """Removing a scholar should cascade to relationships and followups."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)
    repo = ScholarRepository()
    rng = DeterministicRNG(12345)

    # Create and save a scholar
    scholar = repo.generate(rng, "test_scholar")
    state.save_scholar(scholar)

    # Add relationships and followups
    with sqlite3.connect(state._db_path) as conn:
        conn.execute(
            "INSERT INTO relationships (scholar_id, subject_id, feeling) VALUES (?, ?, ?)",
            ("test_scholar", "other_scholar", -0.5)
        )
        conn.execute(
            "INSERT INTO followups (scholar_id, kind, resolve_at, payload) VALUES (?, ?, ?, ?)",
            ("test_scholar", "grudge", datetime.now(timezone.utc).isoformat(), "{}")
        )
        conn.commit()

    # Remove scholar
    state.remove_scholar("test_scholar")

    # Verify cascading deletes
    with sqlite3.connect(state._db_path) as conn:
        relationships = conn.execute(
            "SELECT * FROM relationships WHERE scholar_id = ? OR subject_id = ?",
            ("test_scholar", "test_scholar")
        ).fetchall()
        followups = conn.execute(
            "SELECT * FROM followups WHERE scholar_id = ?",
            ("test_scholar",)
        ).fetchall()

    assert len(relationships) == 0
    assert len(followups) == 0
    assert state.get_scholar("test_scholar") is None


def test_dispatcher_admin_notifier(tmp_path, monkeypatch):
    """Dispatcher backlog alerts should enqueue admin notifications when thresholds are exceeded."""

    messages: list[str] = []

    def notifier(message: str) -> None:
        messages.append(message)

    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_ORDER_PENDING", "1")
    state = GameState(
        db_path=tmp_path / "test.db",
        start_year=1923,
        admin_notifier=notifier,
    )

    state.enqueue_order("mentorship_activation", payload={})
    state.fetch_due_orders("mentorship_activation", datetime.now(timezone.utc))

    assert any("dispatcher backlog" in message.lower() for message in messages)


def test_scholar_not_found_returns_none(tmp_path):
    """Getting a non-existent scholar should return None."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)
    scholar = state.get_scholar("nonexistent")
    assert scholar is None


def test_all_players_with_malformed_data(tmp_path):
    """all_players should handle malformed JSON gracefully."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Insert valid player first
    valid_player = Player(
        id="valid",
        display_name="Valid",
        reputation=5,
        influence={"academia": 1},
        cooldowns={}
    )
    state.upsert_player(valid_player)

    # Insert player with malformed JSON directly
    with sqlite3.connect(state._db_path) as conn:
        conn.execute(
            "INSERT INTO players (id, display_name, reputation, influence, cooldowns) VALUES (?, ?, ?, ?, ?)",
            ("malformed", "Malformed", 0, "not valid json", "{}")
        )
        conn.commit()

    # Should get valid player and skip malformed one
    players = list(state.all_players())
    assert len(players) == 1
    assert players[0].id == "valid"


def test_all_scholars_with_empty_database(tmp_path):
    """all_scholars should return empty iterator for empty database."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)
    scholars = list(state.all_scholars())
    assert scholars == []


def test_expedition_record_persistence(tmp_path):
    """Expedition records should be properly persisted and retrieved."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    record = ExpeditionRecord(
        timestamp=datetime.now(timezone.utc),
        code="EX-001",
        player_id="player1",
        expedition_type="field",
        objective="Test objective",
        team=["scholar1", "scholar2"],
        funding=["academia"],
        prep_depth="deep",
        confidence="certain"
    )

    state.record_expedition(record)

    # Verify persistence
    with sqlite3.connect(state._db_path) as conn:
        row = conn.execute(
            "SELECT * FROM expeditions WHERE code = ?",
            ("EX-001",)
        ).fetchone()

    assert row is not None
    assert row[0] == "EX-001"  # code
    assert row[2] == "player1"  # player_id
    assert json.loads(row[5]) == ["scholar1", "scholar2"]  # team


def test_theory_record_persistence(tmp_path):
    """Theory records should be properly persisted and retrieved."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    record = TheoryRecord(
        timestamp=datetime.now(timezone.utc),
        player_id="player1",
        theory="Test theory",
        confidence="suspect",
        supporters=["scholar1"],
        deadline="2024-12-31"
    )

    state.record_theory(record)

    # Verify persistence
    with sqlite3.connect(state._db_path) as conn:
        row = conn.execute(
            "SELECT * FROM theories WHERE theory = ?",
            ("Test theory",)
        ).fetchone()

    assert row is not None
    assert row[2] == "player1"  # player_id
    assert row[3] == "Test theory"  # theory
    assert row[4] == "suspect"  # confidence


def test_expedition_record_can_be_stored(tmp_path):
    """Expedition records should be storable and retrievable through events."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    record = ExpeditionRecord(
        timestamp=datetime.now(timezone.utc),
        code="EX-002",
        player_id="player2",
        expedition_type="theoretical",
        objective="Test objective 2",
        team=["scholar3"],
        funding=["government"],
        prep_depth="shallow",
        confidence="suspect"
    )

    state.record_expedition(record)
    events = state.export_events()

    # Should have an expedition event
    exp_events = [e for e in events if e.action == "expedition_queued"]
    assert len(exp_events) > 0


def test_theory_record_can_be_stored(tmp_path):
    """Theory records should be storable in database."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    record = TheoryRecord(
        timestamp=datetime.now(timezone.utc),
        player_id="player2",
        theory="Alternative theory",
        confidence="certain",
        supporters=[],
        deadline="2025-01-01"
    )

    state.record_theory(record)

    # Verify stored in database
    with sqlite3.connect(state._db_path) as conn:
        row = conn.execute(
            "SELECT * FROM theories WHERE theory = ?",
            ("Alternative theory",)
        ).fetchone()

    assert row is not None
    assert row[3] == "Alternative theory"


def test_scholar_memories_update(tmp_path):
    """Updating scholar memories should persist correctly."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)
    repo = ScholarRepository()
    rng = DeterministicRNG(12345)

    # Create scholar with memories
    scholar = repo.generate(rng, "s1")

    # Add feelings to memory
    scholar.memory.feelings["other"] = 0.8

    # Add scars to memory (scars are strings)
    scholar.memory.scars.append("betrayal_by_player1")

    state.save_scholar(scholar)

    # Retrieve and verify
    retrieved = state.get_scholar("s1")
    assert "other" in retrieved.memory.feelings
    assert retrieved.memory.feelings["other"] == 0.8
    assert len(retrieved.memory.scars) == 1
    assert "betrayal_by_player1" in retrieved.memory.scars


def test_event_log_append_and_export(tmp_path):
    """Event log should correctly append and export events."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Append multiple events
    events = [
        Event(
            timestamp=datetime.now(timezone.utc),
            action="test_action_1",
            payload={"data": "value1"}
        ),
        Event(
            timestamp=datetime.now(timezone.utc),
            action="test_action_2",
            payload={"data": "value2", "nested": {"key": "value"}}
        )
    ]

    for event in events:
        state.append_event(event)

    # Export and verify
    exported = state.export_events()
    assert len(exported) >= 2

    # Find our test events
    test_events = [e for e in exported if e.action.startswith("test_action")]
    assert len(test_events) == 2
    assert test_events[0].payload["data"] == "value1"
    assert test_events[1].payload["nested"]["key"] == "value"


def test_timeline_year_progression(tmp_path):
    """Timeline year should progress correctly when advanced."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    initial_year = state.current_year()
    assert initial_year == 1923

    # Advance timeline by 365 days (1 year with default settings)
    now = datetime.now(timezone.utc)
    old_year, new_year = state.advance_timeline(now, days_per_year=365)

    # Should stay same year on first advance (not enough time passed)
    # When no advancement happens, old_year is 0 and new_year is current year
    assert old_year == 0
    assert new_year == 1923

    # Manually update last_advanced to force year progression
    past_time = now - timedelta(days=400)
    with sqlite3.connect(state._db_path) as conn:
        conn.execute(
            "UPDATE timeline SET last_advanced = ? WHERE singleton = 1",
            (past_time.isoformat(),)
        )
        conn.commit()

    # Now advance should progress the year
    old_year, new_year = state.advance_timeline(now, days_per_year=365)
    assert new_year > old_year


def test_list_press_releases_ordering(tmp_path):
    """Press releases should be returned in reverse chronological order."""
    from great_work.models import PressRecord, PressRelease

    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Record multiple press releases with different timestamps
    times = [
        datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 3, 10, 0, tzinfo=timezone.utc),
    ]

    for i, timestamp in enumerate(times):
        record = PressRecord(
            timestamp=timestamp,
            release=PressRelease(
                type="test_release",
                headline=f"Headline {i}",
                body=f"Body {i}"
            )
        )
        state.record_press_release(record)

    # Retrieve and verify ordering (most recent first)
    archived = state.list_press_releases()
    assert len(archived) >= 3

    # Check that newer items come first
    test_releases = [item for item in archived if item.release.type == "test_release"]
    assert test_releases[0].release.headline == "Headline 2"
    assert test_releases[1].release.headline == "Headline 1"
    assert test_releases[2].release.headline == "Headline 0"


def test_followup_scheduling_and_retrieval(tmp_path):
    """Followup events should be scheduled and retrieved correctly."""
    state = GameState(db_path=tmp_path / "test.db", start_year=1923)

    # Schedule multiple followups
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    future = datetime.now(timezone.utc) + timedelta(days=365)  # Actually in the future
    now = datetime.now(timezone.utc)

    state.schedule_followup(
        "scholar1",
        "grudge",
        past,
        {"reason": "betrayal"}
    )

    state.schedule_followup(
        "scholar2",
        "reconciliation",
        future,
        {"reason": "apology"}
    )

    # Get due followups (should only get the past one)
    due = state.due_followups(now)
    assert len(due) == 1
    assert due[0][1] == "scholar1"  # scholar_id is second element
    assert due[0][2] == "grudge"    # followup_type is third element
    assert due[0][3]["reason"] == "betrayal"  # payload is fourth element
