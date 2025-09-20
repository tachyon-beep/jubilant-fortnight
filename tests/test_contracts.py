"""Tests for contract upkeep influence sinks."""
import os
from pathlib import Path
import tempfile

from great_work.service import GameService


def _first_scholar(service: GameService):
    for scholar in service.state.all_scholars():
        return scholar
    raise AssertionError("Expected seeded scholars")


def test_contract_upkeep_deducts_influence_and_records_debt():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        scholar = _first_scholar(service)
        scholar.contract["employer"] = "p1"
        scholar.contract["faction"] = "academia"
        service.state.save_scholar(scholar)

        player = service.state.get_player("p1")
        assert player is not None
        player.influence["academia"] = 0
        service.state.upsert_player(player)

        service.advance_digest()

        updated_player = service.state.get_player("p1")
        assert updated_player is not None
        assert updated_player.influence["academia"] == 0

        contract_debts = service.state.list_influence_debts("p1", source="contract")
        assert contract_debts
        debt_entry = contract_debts[0]
        assert debt_entry["amount"] >= service.settings.contract_upkeep_per_scholar


def test_contract_upkeep_pays_down_existing_debt_before_new_charge():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        scholar = _first_scholar(service)
        scholar.contract["employer"] = "p1"
        scholar.contract["faction"] = "academia"
        service.state.save_scholar(scholar)

        # Seed existing debt
        service.state.record_influence_debt(
            player_id="p1",
            faction="academia",
            amount=3,
            now=None,
            source="contract",
        )

        player = service.state.get_player("p1")
        assert player is not None
        player.influence["academia"] = 4
        service.state.upsert_player(player)

        service.advance_digest()

        remaining = service.state.total_influence_debt("p1", source="contract")
        assert remaining <= 1  # prior debt largely cleared by available influence


def test_contract_status_surfaces_in_player_status():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        scholar = _first_scholar(service)
        scholar.contract["employer"] = "p1"
        scholar.contract["faction"] = "academia"
        service.state.save_scholar(scholar)

        status = service.player_status("p1")
        assert status is not None
        contracts = status.get("contracts")
        assert contracts
        assert "academia" in contracts
        assert contracts["academia"]["scholars"] >= 1
