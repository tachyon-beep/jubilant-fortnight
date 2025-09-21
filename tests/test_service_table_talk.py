"""Tests for LLM-enhanced table-talk messages."""
from __future__ import annotations

import os

from great_work.service import GameService

os.environ.setdefault("LLM_MODE", "mock")


def test_post_table_talk_archives_and_tracks(tmp_path):
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    press = service.post_table_talk(
        player_id="storyteller",
        display_name="Storyteller",
        message="The symposium preparations are underway.",
    )

    assert press.type == "table_talk"
    assert press.headline.startswith("Table Talk")
    table_meta = press.metadata.get("table_talk", {})
    assert table_meta
    assert table_meta["player_id"] == "storyteller"
    assert "symposium preparations" in table_meta["message"]
    llm_meta = press.metadata.get("llm", {})
    assert llm_meta
    assert llm_meta.get("persona") == "Storyteller"

    # Ensure archival and events are recorded
    archived = service.state.list_press_releases()
    assert any(item.release.headline == press.headline for item in archived)

    events = service.state.export_events()
    event = next((evt for evt in events if evt.action == "table_talk_post"), None)
    assert event is not None
    assert event.payload["player"] == "storyteller"
    assert "symposium preparations" in event.payload["message"]

    queued = service.state.list_queued_press()
    assert queued, "expected layered table-talk follow-ups to be scheduled"
    assert any(
        item[2]
        .get("metadata", {})
        .get("scheduled", {})
        .get("layer_type")
        in {"academic_gossip", "table_talk_digest"}
        for item in queued
    )
