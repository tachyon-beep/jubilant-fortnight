from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from great_work.moderation import GuardianModerator, ModerationDecision


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_prefilter_blocks_obvious_terms(monkeypatch):
    moderator = GuardianModerator()
    decision = moderator.review(
        "We should murder the rival scholars.",
        surface="test",
        actor="player",
        stage="player_input",
    )
    assert decision.allowed is False
    assert decision.category == "blocklist"


def test_guardian_invoked_when_suspect(monkeypatch):
    moderator = GuardianModerator()

    def fake_urlopen(request, timeout=None):
        payload = {
            "results": [
                {"category": "Hate", "label": "Yes", "score": 0.9},
                {"category": "Violence", "label": "No", "score": 0.01},
            ]
        }
        return DummyResponse(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    moderator._enabled = True
    moderator._always_call_guardian = True

    decision = moderator.review(
        "You are terrible", surface="test", actor="player", stage="player_input"
    )
    assert decision.allowed is False
    assert decision.category == "Hate"
    assert decision.metadata["source"] == "guardian"


def test_guardian_disabled_allows_content(monkeypatch):
    moderator = GuardianModerator()
    moderator._enabled = False
    moderator._always_call_guardian = False

    decision = moderator.review(
        "Just a normal message", surface="test", actor="player", stage="player_input"
    )
    assert decision.allowed is True
