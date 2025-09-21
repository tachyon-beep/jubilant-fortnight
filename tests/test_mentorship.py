"""Test mentorship system implementation."""
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from great_work.models import Player
from great_work.service import GameService


def test_mentorship_flow():
    """Test the complete mentorship flow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ.setdefault("LLM_MODE", "mock")
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
        random.seed(0)
        press = service.queue_mentorship(player_id, scholar.id, "Academia")
        assert press is not None
        assert press.type == "academic_gossip"
        assert "llm" in press.metadata

        queued_press = service.state.list_queued_press()
        mentorship_updates = [payload for _, _, payload in queued_press if payload.get("type") == "mentorship_update"]
        assert mentorship_updates, "Expected mentorship follow-up layers to be queued"
        assert any(
            item.get("metadata", {}).get("track") == "Academia" and item.get("metadata", {}).get("phase") == "queued"
            for item in mentorship_updates
        )

        # Check pending mentorships
        orders = service.state.list_orders(order_type="mentorship_activation", status="pending")
        assert len(orders) == 1
        order = orders[0]
        assert order["actor_id"] == player_id
        assert order["payload"]["scholar_id"] == scholar.id

        # Resolve mentorships through digest
        releases = service._resolve_mentorships()
        assert len(releases) > 0
        assert releases[0].type == "academic_gossip"

        scholar = service.state.get_scholar(scholar.id)
        activation_feeling = scholar.memory.feelings.get(player_id)
        assert activation_feeling is not None and activation_feeling > 0
        history = scholar.contract.get("mentorship_history")
        assert isinstance(history, list)
        assert any(entry.get("event") == "activation" for entry in history)
        assert any(fact.type == "mentorship" for fact in scholar.memory.facts)

        completed_orders = service.state.list_orders(order_type="mentorship_activation")
        assert completed_orders[0]["status"] == "completed"

        # Check active mentorship
        active = service.state.get_active_mentorship(scholar.id)
        assert active is not None
        assert active[1] == player_id

        # Test assign_lab
        press2 = service.assign_lab(player_id, scholar.id, "Industry")
        assert press2 is not None
        assert press2.type == "academic_gossip"

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

        # Advance until mentorship completes (final tier)
        for _ in range(6):
            service._progress_careers()
        scholar = service.state.get_scholar(scholar.id)

        final_feeling = scholar.memory.feelings.get(player_id)
        assert final_feeling is not None and final_feeling > activation_feeling

        history = scholar.contract.get("mentorship_history")
        events = [entry.get("event") for entry in history]
        assert "progression" in events
        assert "completion" in events

        # Mentorship should no longer be active after completion
        assert service.state.get_active_mentorship(scholar.id) is None

        print("Mentorship system test passed!")


if __name__ == "__main__":
    test_mentorship_flow()
