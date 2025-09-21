"""Tests for recruitment odds preview and calculations."""

import os
import tempfile
from pathlib import Path

import pytest

from great_work.service import GameService


def _first_scholar_id(service: GameService) -> str:
    for scholar in service.state.all_scholars():
        return scholar.id
    raise AssertionError("Expected seeded scholars to exist")


def test_recruitment_odds_reflect_influence_and_cooldown() -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        player = service.state.get_player("p1")
        assert player is not None
        player.influence["academia"] = 4  # +20% bonus
        player.cooldowns["recruitment"] = 2
        service.state.upsert_player(player)

        scholar_id = _first_scholar_id(service)
        odds = service.recruitment_odds("p1", scholar_id)

        academia = next(entry for entry in odds if entry["faction"] == "academia")
        expected_bonus = 4 * 0.05
        expected_chance = max(0.05, min(0.95, 0.6 * 0.5 + expected_bonus))

        assert academia["cooldown_active"] is True
        assert academia["cooldown_penalty"] == 0.5
        assert academia["influence_bonus"] == expected_bonus
        assert academia["influence"] == 4
        assert abs(academia["base_chance"] - expected_chance) < 1e-9
        assert academia["relationship_modifier"] == 0
        assert abs(academia["chance"] - expected_chance) < 1e-9


def test_recruitment_odds_sorted_by_chance() -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        player = service.state.get_player("p1")
        assert player is not None
        player.influence.update({"academia": 3, "industry": 1})
        service.state.upsert_player(player)

        scholar_id = _first_scholar_id(service)
        odds = service.recruitment_odds("p1", scholar_id)
        chances = [entry["chance"] for entry in odds]
    assert chances == sorted(chances, reverse=True)


def test_recruitment_layers_schedule_followups() -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        scholar_id = _first_scholar_id(service)
        scholar = service.state.get_scholar(scholar_id)
        assert scholar is not None

        success, _ = service.attempt_recruitment(
            player_id="p1",
            scholar_id=scholar.id,
            faction="academia",
            base_chance=1.0,
        )
        assert success
        queued = service.state.list_queued_press()
        types = {payload["type"] for _, _, payload in queued}
        assert "recruitment_followup" in types
        assert "recruitment_brief" in types


def test_recruitment_relationship_bonus_applies_to_odds() -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        scholar_id = _first_scholar_id(service)
        scholar = service.state.get_scholar(scholar_id)
        assert scholar is not None
        scholar.memory.adjust_feeling("p1", 8.0)
        service.state.save_scholar(scholar)

        odds = service.recruitment_odds("p1", scholar_id)
        academia = next(entry for entry in odds if entry["faction"] == "academia")
        assert academia["relationship_modifier"] > 0
        combined = academia["base_chance"] + academia["relationship_modifier"]
        expected = max(0.05, min(0.95, combined))
        assert abs(academia["chance"] - expected) < 1e-9


def test_recruitment_attempt_uses_relationship_bonus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        scholar_id = _first_scholar_id(service)
        scholar = service.state.get_scholar(scholar_id)
        assert scholar is not None
        scholar.memory.adjust_feeling("p1", 10.0)
        service.state.save_scholar(scholar)

        monkeypatch.setattr(service._rng, "uniform", lambda *_: 0.1)

        success, press = service.attempt_recruitment(
            player_id="p1",
            scholar_id=scholar_id,
            faction="academia",
            base_chance=0.1,
        )

        assert success is True
        assert "Relationship" in press.body
