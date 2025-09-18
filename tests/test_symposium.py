"""Test symposium voting system implementation."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from great_work.service import GameService


def test_symposium_flow():
    """Test the complete symposium flow."""
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
            topic="Test Topic",
            description="Should we test our code before deploying?"
        )
        assert press is not None
        assert "symposium" in press.headline.lower()

        # Check that symposium is active
        current = service.state.get_current_symposium_topic()
        assert current is not None
        topic_id, topic, description, options = current
        assert topic == "Test Topic"
        assert options == [1, 2, 3]

        # Players vote
        vote1 = service.vote_symposium(player1_id, 1)  # Support
        assert vote1 is not None

        vote2 = service.vote_symposium(player2_id, 2)  # Oppose
        assert vote2 is not None

        vote3 = service.vote_symposium(player3_id, 1)  # Support
        assert vote3 is not None

        # Check votes were recorded
        votes = service.state.get_symposium_votes(topic_id)
        assert votes[1] == 2  # Two support votes
        assert votes[2] == 1  # One oppose vote

        # Resolve symposium
        resolution = service.resolve_symposium()
        assert resolution is not None
        assert "resolved" in resolution.headline.lower()
        assert "supported" in resolution.body.lower()  # Should win with 2/3 votes

        # Check symposium is no longer active
        current_after = service.state.get_current_symposium_topic()
        assert current_after is None

        print("Symposium voting system test passed!")


if __name__ == "__main__":
    test_symposium_flow()