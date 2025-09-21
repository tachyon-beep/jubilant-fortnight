"""Smoke tests for Discord channel routing."""
from __future__ import annotations

from great_work.discord_bot import ChannelRouter


def test_channel_router_fallback(monkeypatch):
    for var in [
        "GREAT_WORK_CHANNEL_TABLE_TALK",
        "GREAT_WORK_CHANNEL_GAZETTE",
        "GREAT_WORK_CHANNEL_UPCOMING",
    ]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GREAT_WORK_CHANNEL_ORDERS", "12345")
    router = ChannelRouter.from_env()
    assert router.orders == 12345
    assert router.table_talk is None
