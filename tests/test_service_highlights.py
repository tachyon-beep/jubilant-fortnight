"""Tests for digest highlight generation."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from great_work.models import PressRelease
from great_work.service import GameService


os.environ.setdefault("LLM_MODE", "mock")


def test_create_digest_highlights(tmp_path, monkeypatch):
    monkeypatch.setenv("GREAT_WORK_PRESS_SETTING", "post_cyberpunk_collapse")
    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)

    now = datetime.now(timezone.utc)
    future_time = now + timedelta(hours=3)
    press = PressRelease(
        type="academic_gossip",
        headline="Expedition Follow-up",
        body="Base body",
        metadata={},
    )
    service.state.enqueue_press_release(press, future_time)

    highlight = service.create_digest_highlights(now=now, limit=3, within_hours=24)

    assert highlight is not None
    assert highlight.type == "digest_highlights"
    tone_meta = highlight.metadata.get("tone_seed", {})
    assert tone_meta
    digest_meta = highlight.metadata.get("digest_highlights", {})
    assert digest_meta
    assert digest_meta["items"]

    archived = service.state.list_press_releases()
    assert any(item.release.type == "digest_highlights" for item in archived)
