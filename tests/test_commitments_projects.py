"""Tests for seasonal commitments and faction projects."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

import pytest

from great_work.config import get_settings
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


def test_seasonal_commitment_requires_relationship(tmp_path):
    root = tmp_path / "relationship"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("rival", "Rival")

    player = service.state.get_player("rival")
    assert player is not None
    player.influence["academia"] = 5
    service.state.upsert_player(player)

    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "rival"
    scholar.contract["faction"] = "academia"
    scholar.memory.adjust_feeling("rival", -5.0)
    service.state.save_scholar(scholar)

    with pytest.raises(ValueError):
        service.start_seasonal_commitment(
            "rival",
            "academia",
            tier="C",
            base_cost=3,
            duration_days=4,
        )

    commitment_id = service.start_seasonal_commitment(
        "rival",
        "academia",
        tier="C",
        base_cost=3,
        duration_days=4,
        allow_override=True,
    )
    assert commitment_id > 0


def test_admin_controls_for_commitments_and_projects(tmp_path):
    root = tmp_path / "admin"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("mentor", "Mentor")

    press = service.admin_create_seasonal_commitment(
        admin_id="Admin",
        player_id="mentor",
        faction="academia",
        tier="A",
        base_cost=4,
        duration_days=14,
        reason="Pilot program",
    )
    commitment_id = press.metadata["commitment_id"]
    record = service.state.get_seasonal_commitment(commitment_id)
    assert record is not None
    assert record["status"] == "active"

    press_update = service.admin_update_seasonal_commitment(
        admin_id="Admin",
        commitment_id=commitment_id,
        status="cancelled",
        reason="Player request",
    )
    assert press_update.metadata["status"] == "cancelled"
    record = service.state.get_seasonal_commitment(commitment_id)
    assert record is not None and record["status"] == "cancelled"

    project_press = service.admin_create_faction_project(
        admin_id="Admin",
        name="Observatory",
        faction="academia",
        target_progress=2.5,
        reason="Season kickoff",
    )
    project_id = project_press.metadata["project_id"]
    project = service.state.get_faction_project(project_id)
    assert project is not None and project["status"] == "active"

    project_update = service.admin_update_faction_project(
        admin_id="Admin",
        project_id=project_id,
        status="completed",
        reason="Construction done",
    )
    assert project_update.metadata["status"] == "completed"
    project = service.state.get_faction_project(project_id)
    assert project is not None and project["status"] == "completed"


def test_seasonal_commitment_reprisal_threshold(tmp_path):
    root = tmp_path / "reprisal"
    root.mkdir()
    settings = replace(
        get_settings(),
        seasonal_commitment_duration_days=1,
        seasonal_commitment_min_relationship=-1.0,
        seasonal_commitment_reprisal_threshold=1,
        seasonal_commitment_reprisal_penalty=0,
        seasonal_commitment_reprisal_cooldown_days=0,
    )
    service = GameService(db_path=root / "state.sqlite", settings=settings)
    service.ensure_player("mentor", "Mentor")

    player = service.state.get_player("mentor")
    assert player is not None
    player.influence["academia"] = 0
    service.state.upsert_player(player)

    commitment_id = service.start_seasonal_commitment(
        "mentor",
        "academia",
        base_cost=3,
        duration_days=1,
        allow_override=True,
    )
    assert commitment_id > 0

    service.advance_digest()
    debt_record = service.state.get_influence_debt_record(
        player_id="mentor",
        faction="academia",
        source="seasonal",
    )
    assert debt_record is not None and debt_record["amount"] >= 3

    # Leave player without influence to force a reprisal reputation hit.
    player = service.state.get_player("mentor")
    assert player is not None
    player.influence["academia"] = 0
    service.state.upsert_player(player)

    service.advance_digest()
    debt_after = service.state.get_influence_debt_record(
        player_id="mentor",
        faction="academia",
        source="seasonal",
    )
    assert debt_after is not None
    assert debt_after["reprisal_level"] >= 1
