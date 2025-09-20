"""Test admin tools implementation."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import os

from great_work.models import ConfidenceLevel, ExpeditionPreparation
from great_work.service import GameService


def test_admin_tools():
    """Test admin tool functionality."""
    os.environ.setdefault("LLM_MODE", "mock")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)

        # Create a player
        player_id = "test_player"
        service.ensure_player(player_id, "Test Player")

        # Admin ID
        admin_id = "admin_user"

        # Test reputation adjustment
        press = service.admin_adjust_reputation(
            admin_id=admin_id,
            player_id=player_id,
            delta=10,
            reason="Testing positive adjustment"
        )
        assert press is not None
        assert "reputation" in press.headline.lower()

        player = service.state.get_player(player_id)
        assert player.reputation == 10

        # Test negative adjustment
        press = service.admin_adjust_reputation(
            admin_id=admin_id,
            player_id=player_id,
            delta=-5,
            reason="Testing negative adjustment"
        )
        player = service.state.get_player(player_id)
        assert player.reputation == 5

        # Test influence adjustment
        press = service.admin_adjust_influence(
            admin_id=admin_id,
            player_id=player_id,
            faction="academia",
            delta=20,
            reason="Testing influence boost"
        )
        assert press is not None
        assert "influence" in press.headline.lower()

        player = service.state.get_player(player_id)
        assert player.influence["academia"] == 20

        # Test forced defection
        scholars = list(service.state.all_scholars())
        assert len(scholars) > 0
        scholar = scholars[0]

        press = service.admin_force_defection(
            admin_id=admin_id,
            scholar_id=scholar.id,
            new_faction="industry",
            reason="Testing forced defection"
        )
        assert press is not None
        assert "defection" in press.headline.lower()

        # Reload scholar to check contract
        scholar = service.state.get_scholar(scholar.id)
        assert scholar.contract.get("employer") == "industry"

        # Test expedition cancellation
        # First queue an expedition
        expedition_press = service.queue_expedition(
            code="TEST-001",
            player_id=player_id,
            expedition_type="think_tank",
            objective="Test expedition",
            team=[scholars[0].id],
            funding=["academia"],
            prep_depth="shallow",
            confidence=ConfidenceLevel.SUSPECT,
            preparation=ExpeditionPreparation(
                think_tank_bonus=0,
                expertise_bonus=0,
                site_friction=0,
                political_friction=0,
            )
        )

        # Now cancel it
        press = service.admin_cancel_expedition(
            admin_id=admin_id,
            expedition_code="TEST-001",
            reason="Testing cancellation"
        )
        assert press is not None
        assert "cancelled" in press.headline.lower()

        # Check that expedition is no longer pending
        assert "TEST-001" not in service._pending_expeditions

        # Dispatcher order listing and cancellation
        order_id = service.state.enqueue_order(
            "test_manual",
            actor_id="system",
            subject_id="subject",
            payload={"note": "for testing"},
        )
        orders = service.admin_list_orders(order_type="test_manual", status="pending", limit=5)
        assert any(order["id"] == order_id for order in orders)

        summary = service.admin_cancel_order(order_id=order_id, reason="cleanup")
        assert summary["id"] == order_id
        assert summary["order_type"] == "test_manual"

        cancelled = service.state.get_order(order_id)
        assert cancelled is not None
        assert cancelled["status"] == "cancelled"

        print("Admin tools test passed!")


if __name__ == "__main__":
    test_admin_tools()
