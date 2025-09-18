"""Tests covering the high level game service orchestration."""
from __future__ import annotations

import pytest

from great_work.models import ConfidenceLevel, ExpeditionOutcome, ExpeditionPreparation
from great_work.service import GameService


def build_service(tmp_path):
    """Helper that initialises a fresh :class:`GameService`."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    return service


@pytest.mark.parametrize(
    "confidence, outcome, expected",
    [
        (ConfidenceLevel.SUSPECT, ExpeditionOutcome.SUCCESS, 2),
        (ConfidenceLevel.SUSPECT, ExpeditionOutcome.PARTIAL, 1),
        (ConfidenceLevel.SUSPECT, ExpeditionOutcome.FAILURE, -1),
        (ConfidenceLevel.CERTAIN, ExpeditionOutcome.SUCCESS, 5),
        (ConfidenceLevel.CERTAIN, ExpeditionOutcome.PARTIAL, 2),
        (ConfidenceLevel.CERTAIN, ExpeditionOutcome.FAILURE, -7),
        (ConfidenceLevel.STAKE_CAREER, ExpeditionOutcome.SUCCESS, 15),
        (ConfidenceLevel.STAKE_CAREER, ExpeditionOutcome.PARTIAL, 7),
        (ConfidenceLevel.STAKE_CAREER, ExpeditionOutcome.FAILURE, -25),
    ],
)
def test_confidence_delta_respects_settings(tmp_path, confidence, outcome, expected):
    """Confidence deltas should align with the configured wager table."""

    service = build_service(tmp_path)
    assert service._confidence_delta(confidence, outcome) == expected


def test_queue_and_resolve_expedition_flow(tmp_path):
    """Queueing and resolving an expedition should emit events and press releases."""

    service = build_service(tmp_path)

    # Ensure a known scholar exists for reaction generation.
    assert service.state.get_scholar("s.ironquill") is not None

    preparation = ExpeditionPreparation()

    manifesto = service.queue_expedition(
        code="AR-01",
        player_id="sarah",
        objective="Test the calendar alignment",
        team=["s.ironquill"],
        funding=["academia"],
        preparation=preparation,
        prep_depth="deep",
        confidence=ConfidenceLevel.CERTAIN,
    )

    assert manifesto.type == "research_manifesto"
    assert "Expedition AR-01" in manifesto.headline
    assert "Test the calendar alignment" in manifesto.body

    releases = service.resolve_pending_expeditions()

    assert len(releases) == 1
    report = releases[0]
    assert report.type == "discovery_report"
    assert report.metadata["outcome"] == "success"
    assert "Reputation change: +5" in report.body
    assert "Dr Elara Ironquill" in report.body

    events = service.state.export_events()
    # Launch and resolution events should have been recorded.
    assert len(events) == 2
    assert events[0].action == "launch_expedition"
    assert events[0].payload["code"] == "AR-01"
    assert events[1].action == "expedition_resolved"
    assert events[1].payload["reputation_delta"] == 5
    assert events[1].payload["result"] == "success"

