"""Tests covering the high level game service orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from great_work.models import ConfidenceLevel, ExpeditionOutcome, ExpeditionPreparation
from great_work.service import GameService


def build_service(tmp_path):
    """Helper that initialises a fresh :class:`GameService`."""

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path)
    # Ensure the roster was filled according to the design expectations.
    assert len(list(service.state.all_scholars())) >= 20
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
        expedition_type="field",
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

    assert len(releases) >= 1
    report = releases[0]
    assert report.metadata["outcome"] in {"success", "partial", "landmark"}
    events = service.state.export_events()
    resolution = next(evt for evt in events if evt.action == "expedition_resolved")
    delta = resolution.payload["reputation_delta"]
    assert f"Reputation change: {delta:+}" in report.body
    assert "Dr Elara Ironquill" in report.body

    if len(releases) > 1:
        gossip = releases[1]
        assert gossip.type in {"academic_gossip", "retraction_notice", "discovery_report"}

    # Launch and resolution events should have been recorded.
    assert any(evt.action == "launch_expedition" and evt.payload["code"] == "AR-01" for evt in events)
    assert resolution.payload["reputation_delta"] == delta
    assert resolution.payload["result"] in {"success", "landmark", "partial"}

    # Press releases should have been archived.
    archive = service.state.list_press_releases()
    assert any(item.release.type == "research_manifesto" for item in archive)
    assert any(item.release.type in {"discovery_report", "retraction_notice"} for item in archive)


def test_recruitment_and_cooldown_flow(tmp_path):
    service = build_service(tmp_path)
    service.ensure_player("sarah")

    success, press = service.attempt_recruitment(
        player_id="sarah",
        scholar_id="s.ironquill",
        faction="academia",
        base_chance=1.0,
    )

    assert success is True
    assert press.type == "recruitment_report"
    player = service.state.get_player("sarah")
    assert player is not None
    assert player.influence["academia"] >= 1
    assert player.cooldowns["recruitment"] >= 2

    service._FOLLOWUP_DELAYS["recruitment_grudge"] = timedelta(seconds=0)
    failure, press_fail = service.attempt_recruitment(
        player_id="sarah",
        scholar_id="s.ironquill",
        faction="academia",
        base_chance=0.0,
    )

    assert failure is False
    assert press_fail.type == "recruitment_report"

    followups = service.advance_digest()
    assert any(rel.type == "academic_gossip" for rel in followups)

    status = service.player_status("sarah")
    assert status["reputation"] == service.state.get_player("sarah").reputation
    assert status["influence"]["academia"] <= status["influence_cap"]

    archive = service.state.list_press_releases()
    assert any(item.release.type == "recruitment_report" for item in archive)


def test_defection_offer_and_digest(tmp_path):
    service = build_service(tmp_path)
    scholar_id = "s.ironquill"

    service._FOLLOWUP_DELAYS["defection_return"] = timedelta(seconds=0)
    service._FOLLOWUP_DELAYS["defection_grudge"] = timedelta(seconds=0)

    defected, notice = service.evaluate_defection_offer(
        scholar_id=scholar_id,
        offer_quality=1.0,
        mistreatment=1.0,
        alignment=0.3,
        plateau=0.4,
        new_faction="Foreign Academy",
    )

    assert notice.type == "defection_notice"
    assert defected is True

    refused, second_notice = service.evaluate_defection_offer(
        scholar_id=scholar_id,
        offer_quality=0.0,
        mistreatment=0.0,
        alignment=-0.3,
        plateau=0.0,
        new_faction="Industry",
    )

    assert refused is False
    assert second_notice.type == "defection_notice"

    player = service.state.get_player("sarah")
    if player:
        player.cooldowns["recruitment"] = 2
        service.state.upsert_player(player)
    releases = service.advance_digest()
    assert isinstance(releases, list)
    assert any(rel.type == "academic_gossip" for rel in releases)
    updated = service.state.get_player("sarah")
    if updated:
        assert updated.cooldowns.get("recruitment", 0) <= 1


def test_followup_queue_can_be_seeded(tmp_path):
    service = build_service(tmp_path)
    scholar_id = "s.ironquill"
    service.state.schedule_followup(
        scholar_id,
        "defection_grudge",
        datetime.now(timezone.utc) - timedelta(minutes=5),
        {"faction": "industry"},
    )
    releases = service.advance_digest()
    assert releases
    assert any(rel.type == "academic_gossip" for rel in releases)


def test_reputation_gating_blocks_high_tier_actions(tmp_path):
    service = build_service(tmp_path)
    service.ensure_player("sarah")
    with pytest.raises(PermissionError):
        service.queue_expedition(
            code="AR-99",
            player_id="sarah",
            expedition_type="great_project",
            objective="Ambitious", 
            team=["s.ironquill"],
            funding=["academia"],
            preparation=ExpeditionPreparation(),
            prep_depth="deep",
            confidence=ConfidenceLevel.CERTAIN,
        )

