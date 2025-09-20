"""Tests for long-tail influence sinks (investments and endowments)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from great_work.service import GameService


def build_service(root: Path) -> GameService:
    os.environ.setdefault("LLM_MODE", "mock")
    db_path = root / "state.sqlite"
    return GameService(db_path=db_path)


def test_faction_investment_boosts_relationship(tmp_path: Path) -> None:
    root = tmp_path / "invest"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("investor", "Investor")

    player = service.state.get_player("investor")
    assert player is not None
    player.influence["academia"] = 12
    service.state.upsert_player(player)

    scholar = next(iter(service.state.all_scholars()))
    scholar.contract["employer"] = "investor"
    scholar.contract["faction"] = "academia"
    baseline = scholar.memory.feelings.get("investor", 0.0)
    service.state.save_scholar(scholar)

    press = service.invest_in_faction(
        "investor",
        "academia",
        amount=6,
        program="Museum Wing",
    )
    assert press.type == "faction_investment"

    updated_player = service.state.get_player("investor")
    assert updated_player is not None
    assert updated_player.influence["academia"] == 6

    refreshed = service.state.get_scholar(scholar.id)
    assert refreshed is not None
    assert refreshed.memory.feelings.get("investor", 0.0) > baseline

    records = service.list_faction_investments("investor")
    assert records and records[0]["amount"] == 6


def test_archive_endowment_reduces_debt_and_grants_reputation(tmp_path: Path) -> None:
    root = tmp_path / "endow"
    root.mkdir()
    service = build_service(root)
    service.ensure_player("donor", "Donor")

    player = service.state.get_player("donor")
    assert player is not None
    player.influence["academia"] = 15
    service.state.upsert_player(player)

    now = datetime.now(timezone.utc)
    service.state.record_symposium_debt(
        player_id="donor",
        faction="academia",
        amount=5,
        now=now,
    )

    press = service.endow_archive(
        "donor",
        amount=12,
        faction="academia",
        program="Archive Stacks",
    )
    assert press.type == "archive_endowment"

    updated_player = service.state.get_player("donor")
    assert updated_player is not None
    assert updated_player.influence["academia"] == 3
    expected_rep = service.settings.archive_endowment_reputation_bonus
    assert updated_player.reputation >= expected_rep

    debt_record = service.state.get_influence_debt_record(
        player_id="donor",
        faction="academia",
        source="symposium",
    )
    assert debt_record is None

    endowments = service.list_archive_endowments("donor")
    assert endowments and endowments[0]["amount"] == 12
