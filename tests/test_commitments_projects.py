"""Tests for seasonal commitments and faction projects."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from great_work.service import GameService


def build_service(root: Path) -> GameService:
    os.environ.setdefault("LLM_MODE", "mock")
    db_path = root / "state.sqlite"
    return GameService(db_path=db_path)


def test_seasonal_commitment_relationship_reduces_cost(tmp_path):
    root = tmp_path / "commitment"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("mentor", "Mentor")

    player = service.state.get_player("mentor")
    assert player is not None
    player.influence["academia"] = 10
    service.state.upsert_player(player)

    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "mentor"
    scholar.contract["faction"] = "academia"
    scholar.memory.adjust_feeling("mentor", 10.0)
    service.state.save_scholar(scholar)

    commitment_id = service.start_seasonal_commitment(
        "mentor",
        "academia",
        tier="A",
        base_cost=4,
        duration_days=5,
    )
    assert commitment_id > 0

    before = service.state.get_player("mentor").influence["academia"]
    releases = service.advance_digest()
    after = service.state.get_player("mentor").influence["academia"]
    assert any(rel.type == "seasonal_commitment_update" for rel in releases)
    assert after < before
    assert after >= before - 4  # relationship should reduce cost

    status = service.player_status("mentor")
    assert status.get("commitments")


def test_faction_project_progress_uses_relationship(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("mentor", "Mentor")

    player = service.state.get_player("mentor")
    assert player is not None
    player.influence["academia"] = 10
    service.state.upsert_player(player)

    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "mentor"
    scholar.contract["faction"] = "academia"
    scholar.memory.adjust_feeling("mentor", 10.0)
    service.state.save_scholar(scholar)

    project_id = service.start_faction_project(
        name="Sky Array",
        faction="academia",
        target_progress=1.0,
    )
    assert project_id > 0

    releases = service.advance_digest()
    assert any(rel.type == "faction_project_update" for rel in releases)

    projects = service.list_faction_projects(include_completed=True)
    project = next(proj for proj in projects if proj["id"] == project_id)
    assert project["progress"] > 0
