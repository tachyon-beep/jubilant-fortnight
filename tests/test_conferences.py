"""Test conference system implementation."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from great_work.models import ConfidenceLevel
from great_work.service import GameService


def test_conference_flow():
    """Test the complete conference flow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)

        # Create a player
        player_id = "test_player"
        service.ensure_player(player_id, "Test Player")

        # Get some scholars for supporters and opposition
        scholars = list(service.state.all_scholars())
        assert len(scholars) >= 4
        supporters = [scholars[0].id, scholars[1].id]
        opposition = [scholars[2].id, scholars[3].id]

        # First submit a theory
        theory_press = service.submit_theory(
            player_id=player_id,
            theory="The moon is made of cheese",
            confidence=ConfidenceLevel.CERTAIN,
            supporters=supporters,
            deadline="End of time",
        )
        assert theory_press is not None

        # Get the theory ID (should be 1 as first theory)
        theories = service.state.list_theories()
        assert len(theories) > 0
        theory_id, theory_record = theories[0]

        # Launch a conference
        conf_press = service.launch_conference(
            player_id=player_id,
            theory_id=theory_id,
            confidence=ConfidenceLevel.SUSPECT,
            supporters=supporters,
            opposition=opposition,
        )
        assert conf_press is not None
        assert "conference" in conf_press.body.lower() or "debate" in conf_press.body.lower()

        # Check pending conferences
        orders = service.state.list_orders(order_type="conference_resolution", status="pending")
        assert len(orders) == 1
        order = orders[0]
        assert order["actor_id"] == player_id
        assert order["payload"]["theory_id"] == theory_id
        assert order["payload"]["supporters"] == supporters
        assert order["payload"]["opposition"] == opposition

        # Resolve conferences
        releases = service.resolve_conferences()
        assert len(releases) > 0
        assert "conference" in releases[0].body.lower()

        # Check that conference was resolved
        orders_after = service.state.list_orders(order_type="conference_resolution")
        assert orders_after[0]["status"] == "completed"

        # Check player reputation was affected
        player = service.state.get_player(player_id)
        # Reputation should have changed (could be positive or negative based on outcome)
        assert player.reputation != 0

        print("Conference system test passed!")


if __name__ == "__main__":
    test_conference_flow()
