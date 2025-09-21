"""Test symposium voting system implementation."""

import os
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import pytest

from great_work.config import get_settings
from great_work.service import GameService


def build_service(
    tmp_path,
    *,
    first_reminder: float = 12.0,
    escalation: float = 24.0,
    max_backlog: int | None = None,
    max_per_player: int | None = None,
    expiry_days: int | None = None,
    pledge_base: int | None = None,
    debt_threshold: int | None = None,
    debt_penalty: int | None = None,
    debt_cooldown_days: int | None = None,
) -> GameService:
    settings = get_settings()
    custom_settings = replace(
        settings,
        symposium_first_reminder_hours=first_reminder,
        symposium_escalation_hours=escalation,
        symposium_max_backlog=max_backlog or settings.symposium_max_backlog,
        symposium_max_per_player=max_per_player or settings.symposium_max_per_player,
        symposium_proposal_expiry_days=expiry_days
        or settings.symposium_proposal_expiry_days,
        symposium_pledge_base=pledge_base or settings.symposium_pledge_base,
        symposium_debt_reprisal_threshold=debt_threshold
        or settings.symposium_debt_reprisal_threshold,
        symposium_debt_reprisal_penalty=debt_penalty
        or settings.symposium_debt_reprisal_penalty,
        symposium_debt_reprisal_cooldown_days=debt_cooldown_days
        or settings.symposium_debt_reprisal_cooldown_days,
    )
    return GameService(db_path=tmp_path, settings=custom_settings)


def test_symposium_flow():
    """Test the complete symposium flow."""
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)

        # Create players
        player1_id = "player1"
        player2_id = "player2"
        player3_id = "player3"
        service.ensure_player(player1_id, "Player One")
        service.ensure_player(player2_id, "Player Two")
        service.ensure_player(player3_id, "Player Three")

        # Start a symposium
        press = service.start_symposium(
            topic="Test Topic", description="Should we test our code before deploying?"
        )
        assert press is not None
        assert "symposium" in press.headline.lower()
        assert "[MOCK]" in press.body
        assert (
            "llm" in press.metadata
            and press.metadata["llm"]["persona"] == "The Academy"
        )
        pledge_meta = press.metadata.get("pledge")
        assert pledge_meta is not None
        assert pledge_meta["base"] == service.settings.symposium_pledge_base
        assert pledge_meta["players"] == 3

        # Check that symposium is active
        current = service.state.get_current_symposium_topic()
        assert current is not None
        topic_id, topic, description, proposal_id, options = current
        assert topic == "Test Topic"
        assert options == [1, 2, 3]
        assert proposal_id is None

        # Players vote
        vote1 = service.vote_symposium(player1_id, 1)  # Support
        assert vote1 is not None
        assert "[MOCK]" in vote1.body

        vote2 = service.vote_symposium(player2_id, 2)  # Oppose
        assert vote2 is not None
        assert "[MOCK]" in vote2.body

        vote3 = service.vote_symposium(player3_id, 1)  # Support
        assert vote3 is not None
        assert "[MOCK]" in vote3.body

        # Check votes were recorded
        votes = service.state.get_symposium_votes(topic_id)
        assert votes[1] == 2  # Two support votes
        assert votes[2] == 1  # One oppose vote

        # Resolve symposium
        resolution = service.resolve_symposium()
        assert resolution is not None
        assert "resolved" in resolution.headline.lower()
        assert "[MOCK]" in resolution.body
        assert resolution.metadata["winner"] == "1"
        assert resolution.metadata["votes"][1] == 2
        assert not resolution.metadata.get("non_voters")
        assert resolution.metadata.get("penalties") == []
        pledge_record = service.state.get_symposium_pledge(
            topic_id=topic_id,
            player_id=player1_id,
        )
        assert pledge_record is not None
        assert pledge_record["status"] == "fulfilled"

        # Check symposium is no longer active
        current_after = service.state.get_current_symposium_topic()
        assert current_after is None

        print("Symposium voting system test passed!")


def test_symposium_proposal_selection():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("proposer", "Proposer")
        service.ensure_player("voter", "Voter")

        press = service.submit_symposium_proposal(
            player_id="proposer",
            topic="Player Topic",
            description="A player-driven debate",
        )
        assert press.metadata["proposal_id"]
        assert "symposium" in press.headline.lower()
        assert "expires_at" in press.metadata

        proposals = service.list_symposium_proposals(limit=5)
        assert proposals
        assert proposals[0]["topic"] == "Player Topic"
        assert proposals[0]["expires_at"] is not None

        announcement = service.start_symposium()
        assert "player topic" in announcement.headline.lower()
        current = service.state.get_current_symposium_topic()
        assert current is not None
        topic_id, topic, description, proposal_id, _ = current
        assert proposal_id is not None

        proposal_meta = service.state.get_symposium_proposal(proposal_id)
        assert proposal_meta is not None
        assert proposal_meta["status"] == "selected"


def test_symposium_reminders_for_non_voters():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = build_service(db_path, first_reminder=0.0, escalation=24.0)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        service.start_symposium(topic="Reminder Test", description="Testing reminders")

        releases = service.advance_digest()
        reminder = next(rel for rel in releases if rel.type == "symposium_reminder")
        assert (
            reminder.metadata["pledge_amount"] == service.settings.symposium_pledge_base
        )

        # After voting, reminders should be cleared
        service.vote_symposium("p1", 1)
        pending_orders = self_state_orders_for_topic(service, "symposium_vote_reminder")
        assert all(order["actor_id"] != "p1" for order in pending_orders)


def test_symposium_proposal_limits():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = build_service(
            db_path,
            max_backlog=4,
            max_per_player=2,
        )
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        # Player capped at two active proposals
        service.submit_symposium_proposal("p1", "Topic A", "Desc")
        service.submit_symposium_proposal("p1", "Topic B", "Desc")
        with pytest.raises(ValueError):
            service.submit_symposium_proposal("p1", "Topic C", "Desc")

        # Fill backlog
        service.submit_symposium_proposal("p2", "Topic D", "Desc")
        service.submit_symposium_proposal("p2", "Topic E", "Desc")
        with pytest.raises(ValueError):
            service.submit_symposium_proposal("p2", "Topic F", "Desc")


def test_symposium_reprimand_followup():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = build_service(
            db_path,
            debt_threshold=1,
            debt_penalty=0,
            debt_cooldown_days=0,
        )
        player_id = "debtor"
        service.ensure_player(player_id, "Debt Holder")

        now = datetime.now(timezone.utc)
        service.state.record_symposium_debt(
            player_id=player_id,
            faction="academia",
            amount=5,
            now=now,
        )

        player = service.state.get_player(player_id)
        result = service._settle_symposium_debts(player, now)
        assert result["reprisals"], "Expected reprisal events"

        orders = service.admin_list_orders(
            order_type="followup:symposium_reprimand", limit=5
        )
        assert orders, "Expected symposium reprimand follow-up order"

        releases = service._resolve_followups()
        reprimand_press = next(
            (press for press in releases if press.type == "symposium_reprimand"), None
        )
        assert reprimand_press is not None
        assert "reprisal" in reprimand_press.body.lower()


def test_symposium_proposal_expiry_cleanup():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = build_service(db_path, expiry_days=7)
        service.ensure_player("p1", "Player One")

        press = service.submit_symposium_proposal("p1", "Short Lived", "Desc")
        proposal_id = press.metadata["proposal_id"]
        future = datetime.now(timezone.utc) + timedelta(days=8)
        expired = service.state.expire_symposium_proposals(future)
        assert proposal_id in expired
        pending = service.list_symposium_proposals()
        assert all(p["id"] != proposal_id for p in pending)


def test_symposium_penalty_and_grace():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        player_one = service.state.get_player("p1")
        assert player_one is not None
        initial_influence = 6
        player_one.influence["academia"] = initial_influence
        service.state.upsert_player(player_one)

        # First symposium, Player Two votes, Player One skips (grace should absorb)
        service.start_symposium(topic="Week One", description="Test")
        topic_id, *_ = service.state.get_current_symposium_topic()
        service.vote_symposium("p2", 1)
        first_resolution = service.resolve_symposium()
        penalties = first_resolution.metadata["penalties"]
        assert penalties
        first_penalty = next(p for p in penalties if p["player_id"] == "p1")
        assert first_penalty["status"] == "waived"
        assert first_penalty["deducted"] == 0

        pledge_record = service.state.get_symposium_pledge(
            topic_id=topic_id, player_id="p1"
        )
        assert pledge_record["status"] == "waived"

        # Reduce influence to force debt on next miss
        player_one = service.state.get_player("p1")
        player_one.influence["academia"] = 1
        service.state.upsert_player(player_one)

        # Second symposium, Player One misses again -> debt recorded
        service.start_symposium(topic="Week Two", description="Test")
        topic_id_two, *_ = service.state.get_current_symposium_topic()
        service.vote_symposium("p2", 1)
        second_resolution = service.resolve_symposium()
        penalties_two = second_resolution.metadata["penalties"]
        penalty_two = next(p for p in penalties_two if p["player_id"] == "p1")
        assert penalty_two["status"] == "debt"
        assert penalty_two["remaining_debt"] > 0
        assert penalty_two["deducted"] <= 1

        updated_player = service.state.get_player("p1")
        assert updated_player.influence["academia"] == 0
        pledge_record_two = service.state.get_symposium_pledge(
            topic_id=topic_id_two, player_id="p1"
        )
        assert pledge_record_two["status"] == "debt"

        # Pay off debt before Week Three
        outstanding = service.state.total_symposium_debt("p1")
        repayment_player = service.state.get_player("p1")
        repayment_player.influence["academia"] = outstanding
        service.state.upsert_player(repayment_player)

        service.start_symposium(topic="Week Three", description="Test")
        status = service.symposium_pledge_status("p1")
        assert status["outstanding_debt"] == 0


def test_symposium_pledge_status_summary():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        # Initial symposium
        service.start_symposium(topic="Week One", description="Summary Test")
        status_before = service.symposium_pledge_status("p1")
        assert status_before["current"] is not None
        assert status_before["current"]["status"] in {"pending", "none"}

        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        status_after_first = service.symposium_pledge_status("p1")
        assert any(
            entry["status"] == "waived" for entry in status_after_first["history"]
        )

        # Second symposium to trigger debt
        player_one = service.state.get_player("p1")
        player_one.influence["academia"] = 1
        service.state.upsert_player(player_one)

        service.start_symposium(topic="Week Two", description="Summary Test")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        status_final = service.symposium_pledge_status("p1")
        assert status_final["miss_streak"] >= 1
        assert status_final["outstanding_debt"] > 0
        assert any(entry["status"] == "debt" for entry in status_final["history"])


def test_symposium_debt_auto_settle():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        player_one = service.state.get_player("p1")
        player_one.influence["academia"] = 1
        service.state.upsert_player(player_one)

        service.start_symposium(topic="Week One", description="Debt Test")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        # Second week to generate debt after grace is consumed
        service.start_symposium(topic="Week Two", description="Debt Test")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        outstanding = service.state.total_symposium_debt("p1")
        assert outstanding > 0

        payoff_player = service.state.get_player("p1")
        payoff_player.influence["academia"] = outstanding
        service.state.upsert_player(payoff_player)

        service.start_symposium(topic="Week Two", description="Debt Test")
        status = service.symposium_pledge_status("p1")
        assert status["outstanding_debt"] == 0


def test_symposium_proposal_scoring_prefers_fresh_player():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        # Initial proposal from player one, selected and resolved
        service.submit_symposium_proposal("p1", "Legacy Topic", "Explore scoring")
        announcement = service.start_symposium()
        assert announcement.metadata["proposal_id"] is not None
        service.vote_symposium("p1", 1)
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        # New proposals from both players
        service.submit_symposium_proposal(
            "p1", "Repeat Topic", "Should be deprioritised"
        )
        service.submit_symposium_proposal("p2", "Fresh Topic", "New voice")

        next_announcement = service.start_symposium()
        assert next_announcement.metadata["proposal_id"] is not None
        selected = service.state.get_symposium_proposal(
            next_announcement.metadata["proposal_id"]
        )
    assert selected["player_id"] == "p2"


def test_symposium_backlog_report_scores():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        service.submit_symposium_proposal("p1", "Legacy Topic", "History")
        service.start_symposium()
        service.vote_symposium("p1", 1)
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        service.submit_symposium_proposal("p1", "Repeat", "older")
        service.submit_symposium_proposal("p2", "Fresh", "new")
        service.start_symposium()

        report = service.symposium_backlog_report()
        assert report["backlog_size"] >= 0
        assert "debts" in report
        assert "config" in report and "max_age_days" in report["config"]
        scoring = report["scoring"]
        if scoring:
            top = scoring[0]
            assert top["display_name"] == "Player Two"
            assert "age_contribution" in top
            assert "fresh_bonus" in top
            assert "repeat_penalty" in top


def test_symposium_debt_reprisal_triggers_penalty():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = build_service(
            db_path,
            pledge_base=5,
            debt_threshold=4,
            debt_penalty=2,
            debt_cooldown_days=0,
        )
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        player_one = service.state.get_player("p1")
        player_one.influence["academia"] = 0
        service.state.upsert_player(player_one)

        # First symposium (grace)
        service.start_symposium(topic="Week One", description="Reprisal")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()


def test_symposium_backlog_report_includes_debt_metadata():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        player_one = service.state.get_player("p1")
        assert player_one is not None
        player_one.influence["academia"] = 0
        service.state.upsert_player(player_one)

        # First miss consumes grace
        service.start_symposium(topic="Debt Week", description="Transparency")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        # Second miss creates debt
        service.start_symposium(topic="Debt Week 2", description="Transparency")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        report = service.symposium_backlog_report()
        debts = report.get("debts") or []
        assert isinstance(debts, list)
        assert report.get("debt_totals", {}).get("total_outstanding", 0) >= 0
        if debts:
            debt_row = debts[0]
            assert "reprisal_level" in debt_row
            assert "next_reprisal_at" in debt_row
            assert "cooldown_days" in debt_row


def test_symposium_status_reports_debt_details():
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")
        service.ensure_player("p2", "Player Two")

        player_one = service.state.get_player("p1")
        assert player_one is not None
        player_one.influence["academia"] = 0
        service.state.upsert_player(player_one)

        # First miss uses grace window
        service.start_symposium(topic="Debt Detail", description="Status command")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        # Second miss triggers debt
        service.start_symposium(topic="Debt Detail 2", description="Status command")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        status = service.symposium_pledge_status("p1")
        debts = status.get("debts") or []
        assert debts, "Expected symposium debt entry"
        debt_info = debts[0]
        assert "next_reprisal_at" in debt_info
        assert "reprisal_level" in debt_info
        assert "cooldown_days" in debt_info

        # Second symposium to accrue debt
        service.start_symposium(topic="Week Two", description="Reprisal")
        service.vote_symposium("p2", 1)
        service.resolve_symposium()

        initial_reputation = service.state.get_player("p1").reputation

        # Third symposium triggers reprisal (no influence to pay)
        service.start_symposium(topic="Week Three", description="Reprisal")
        status = service.symposium_pledge_status("p1")
        assert (
            status["outstanding_debt"]
            >= service.settings.symposium_debt_reprisal_threshold
        )
        updated_player = service.state.get_player("p1")
        assert updated_player.reputation == initial_reputation - 1
        debt_record = service.state.get_symposium_debt_record(
            player_id="p1", faction="academia"
        )
        if debt_record:
            assert debt_record["reprisal_level"] >= 1


def self_state_orders_for_topic(
    service: GameService, order_type: str
) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc) + timedelta(days=1)
    # Borrow GameState helper to pull pending orders
    orders = service.state.fetch_due_orders(order_type, now)
    return orders


if __name__ == "__main__":
    test_symposium_flow()
