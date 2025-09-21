"""Tests for table-talk layered press."""
import os
import tempfile
from pathlib import Path

from great_work.service import GameService


def test_table_talk_schedules_followups() -> None:
    os.environ["LLM_MODE"] = "mock"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        service = GameService(db_path)
        service.ensure_player("p1", "Player One")

        press = service.post_table_talk(
            player_id="p1",
            display_name="Player One",
            message="Testing layered reactions",
        )
        assert press.type == "table_talk"

        queued = service.state.list_queued_press()
        types = {payload["type"] for _, _, payload in queued}
        assert "table_talk_digest" in types
        assert "table_talk_roundup" in types
