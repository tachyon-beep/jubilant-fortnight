"""Tests covering the high level game service orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import os
import sqlite3

import pytest

from great_work.models import ConfidenceLevel, ExpeditionOutcome, ExpeditionPreparation
from great_work.service import GameService


def build_service(tmp_path):
    """Helper that initialises a fresh :class:`GameService`."""

    os.environ.setdefault("LLM_MODE", "mock")
    os.environ.setdefault("LLM_RETRY_SCHEDULE", "1,5,15")
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
    assert "[MOCK]" in manifesto.body
    assert "llm" in manifesto.metadata
    assert manifesto.metadata["llm"]["persona"] == "sarah"

    releases = service.resolve_pending_expeditions()

    assert len(releases) >= 1
    report = releases[0]
    assert report.metadata["outcome"] in {"success", "partial", "landmark"}
    events = service.state.export_events()
    resolution = next(evt for evt in events if evt.action == "expedition_resolved")
    delta = resolution.payload["reputation_delta"]
    assert f"Reputation change: {delta:+}" in report.body or "[MOCK]" in report.body
    assert "[MOCK]" in report.body
    assert "llm" in report.metadata
    assert report.metadata["llm"]["persona"] == "sarah"

    # Launch and resolution events should have been recorded.
    assert any(evt.action == "launch_expedition" and evt.payload["code"] == "AR-01" for evt in events)
    assert resolution.payload["reputation_delta"] == delta
    assert resolution.payload["result"] in {"success", "landmark", "partial"}

    # Press releases should have been archived.
    archive = service.state.list_press_releases()
    assert any(item.release.type == "research_manifesto" for item in archive)
    assert any(item.release.type in {"discovery_report", "retraction_notice"} for item in archive)

    queued = service.state.list_queued_press()
    future_time = datetime.now(timezone.utc) + timedelta(hours=3)
    scheduled = service.release_scheduled_press(future_time)
    if queued:
        assert scheduled, "Scheduled press should release when due"
        for item in scheduled:
            assert "scheduled" in item.metadata
            assert "delay_minutes" in item.metadata["scheduled"]
    assert not service.state.list_queued_press()


def test_llm_activity_records_telemetry(monkeypatch, tmp_path):
    os.environ.setdefault("LLM_MODE", "mock")

    class StubTelemetry:
        def __init__(self) -> None:
            self.llm_calls = []
            self.system_events = []

        def track_llm_activity(self, press_type, success, duration_ms, persona=None, error=None):
            self.llm_calls.append(
                {
                    "press_type": press_type,
                    "success": success,
                    "persona": persona,
                    "error": error,
                    "duration_ms": duration_ms,
                }
            )

        def track_system_event(self, event, *, source=None, reason=None):
            self.system_events.append(
                {"event": event, "source": source, "reason": reason}
            )

    stub = StubTelemetry()
    monkeypatch.setattr("great_work.service.get_telemetry", lambda: stub)

    db_path = tmp_path / "telemetry.sqlite"
    service = GameService(db_path=db_path)

    preparation = ExpeditionPreparation()
    service.queue_expedition(
        code="TL-01",
        player_id="sarah",
        expedition_type="field",
        objective="Trace LLM hooks",
        team=["s.ironquill"],
        funding=["academia"],
        preparation=preparation,
        prep_depth="standard",
        confidence=ConfidenceLevel.CERTAIN,
    )

    assert stub.llm_calls, "Expected LLM telemetry to capture expedition manifesto enhancement"
    call = stub.llm_calls[0]
    assert call["press_type"] == "research_manifesto"
    assert call["success"] is True
    assert call["persona"] == "sarah"
    assert call["error"] is None


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


def test_digest_emits_timeline_update(tmp_path):
    service = build_service(tmp_path)
    days_per_year = service.settings.time_scale_days_per_year
    rewind = datetime.now(timezone.utc) - timedelta(days=days_per_year)
    with sqlite3.connect(service.state._db_path) as conn:
        conn.execute(
            "UPDATE timeline SET last_advanced = ?, current_year = ? WHERE singleton = 1",
            (rewind.isoformat(), service.settings.timeline_start_year),
        )
        conn.commit()

    releases = service.advance_digest()

    assert any(rel.type == "timeline_update" for rel in releases)
    assert service.state.current_year() >= service.settings.timeline_start_year + 1


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
    assert "llm" in notice.metadata
    assert "llm" in second_notice.metadata
    assert notice.metadata["llm"]["persona"] == "Dr Elara Ironquill"
    assert second_notice.metadata["llm"]["persona"] == "Dr Elara Ironquill"

    queued = service.state.list_queued_press()
    assert queued, "Expected defection follow-ups to be scheduled"
    scheduled_followups = service.release_scheduled_press(datetime.now(timezone.utc) + timedelta(hours=4))
    assert scheduled_followups, "Scheduled defection follow-ups should release"
    assert any(rel.type == "faction_statement" for rel in scheduled_followups)
    assert any(rel.type == "academic_gossip" for rel in scheduled_followups)
    assert not service.state.list_queued_press()

    archive = service.state.list_press_releases(limit=50)
    assert any(item.release.type == "faction_statement" for item in archive)
    assert any(item.release.type == "academic_gossip" for item in archive)

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


def test_wager_reference_exposes_thresholds_and_bounds(tmp_path):
    service = build_service(tmp_path)

    reference = service.wager_reference()

    assert "wagers" in reference
    assert (
        reference["wagers"][ConfidenceLevel.STAKE_CAREER.value]["penalty"]
        == service.settings.confidence_wagers[ConfidenceLevel.STAKE_CAREER.value]["penalty"]
    )
    assert (
        reference["wagers"][ConfidenceLevel.STAKE_CAREER.value]["triggers_recruitment_cooldown"]
        is True
    )

    thresholds = reference["action_thresholds"]
    assert thresholds["recruitment"] == service.settings.action_thresholds["recruitment"]

    bounds = reference["reputation_bounds"]
    assert bounds["min"] == service.settings.reputation_bounds["min"]
    assert bounds["max"] == service.settings.reputation_bounds["max"]
