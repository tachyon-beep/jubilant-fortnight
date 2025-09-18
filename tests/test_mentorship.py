"""Test mentorship system implementation."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from great_work.models import Player
from great_work.service import GameService


def test_mentorship_flow():
    """Test the complete mentorship flow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)

        # Service auto-initializes scholars on creation
        # Create a player
        player_id = "test_player"
        service.ensure_player(player_id, "Test Player")

        # Get a scholar
        scholars = list(service.state.all_scholars())
        assert len(scholars) > 0
        scholar = scholars[0]

        # Queue mentorship
        press = service.queue_mentorship(player_id, scholar.id, "Academia")
        assert press is not None
        assert "mentorship" in press.body.lower() or "guide" in press.body.lower()

        # Check pending mentorships
        pending = service.state.get_pending_mentorships()
        assert len(pending) == 1
        assert pending[0][1] == player_id
        assert pending[0][2] == scholar.id

        # Resolve mentorships through digest
        releases = service._resolve_mentorships()
        assert len(releases) > 0
        assert "commenced" in releases[0].body.lower()

        # Check active mentorship
        active = service.state.get_active_mentorship(scholar.id)
        assert active is not None
        assert active[1] == player_id

        # Test assign_lab
        press2 = service.assign_lab(player_id, scholar.id, "Industry")
        assert press2 is not None
        assert "Industry" in press2.body

        # Reload scholar to check career track change
        scholar = service.state.get_scholar(scholar.id)
        assert scholar.career["track"] == "Industry"

        # Test career progression with mentor
        releases = service._progress_careers()
        # First time won't advance (needs 3 ticks)
        assert len(releases) == 0

        # Progress time and try again
        for _ in range(3):
            releases = service._progress_careers()

        # Should have advanced after 3 ticks
        scholar = service.state.get_scholar(scholar.id)
        assert scholar.career.get("tier") == "Director"  # Second tier of Industry track

        print("Mentorship system test passed!")


if __name__ == "__main__":
    test_mentorship_flow()