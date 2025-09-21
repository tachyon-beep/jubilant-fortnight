"""Tests covering the high level game service orchestration."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest

from great_work.models import (
    ConfidenceLevel,
    ExpeditionOutcome,
    ExpeditionPreparation,
    OfferRecord,
    PressRelease,
)
from great_work.moderation import ModerationDecision
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


def test_submit_theory_moderation_blocked(tmp_path):
    service = build_service(tmp_path)

    class BlockingModerator:
        def review(self, text, *, surface, actor, stage):
            return ModerationDecision(
                allowed=False,
                severity="block",
                reason="disallowed",
                category="test",
                metadata={"source": "test"},
            )

    service._moderator = BlockingModerator()
    service.ensure_player("ada", "Ada")

    with pytest.raises(GameService.ModerationRejectedError):
        service.submit_theory(
            player_id="ada",
            theory="Super weapon theory",
            confidence=ConfidenceLevel.SUSPECT,
            supporters=[],
            deadline="soon",
        )


def test_llm_output_moderation_fallback(tmp_path, monkeypatch):
    service = build_service(tmp_path)

    class StageModerator:
        def review(self, text, *, surface, actor, stage):
            if stage == "llm_output":
                return ModerationDecision(
                    allowed=False,
                    severity="block",
                    reason="guardian",
                    category="guardian",
                    metadata={"source": "guardian"},
                )
            return ModerationDecision(True, metadata={"source": "prefilter"})

    service._moderator = StageModerator()

    monkeypatch.setattr(
        "great_work.service.enhance_press_release_sync",
        lambda *args, **kwargs: "Generated output with issues",
    )

    press = PressRelease(
        type="test_press",
        headline="Test Headline",
        body="Original body",
        metadata={},
    )

    result = service._enhance_press_release(
        press,
        base_body="Original body",
        persona_name=None,
        persona_traits=None,
        extra_context={"event_type": "unit_test"},
    )

    assert result.body == "Original body"
    moderation_meta = result.metadata.get("moderation")
    assert moderation_meta is not None
    assert moderation_meta.get("blocked") is True


def test_llm_activity_records_telemetry(monkeypatch, tmp_path):
    os.environ.setdefault("LLM_MODE", "mock")

    class StubTelemetry:
        def __init__(self) -> None:
            self.llm_calls = []
            self.system_events = []

        def track_llm_activity(
            self, press_type, success, duration_ms, persona=None, error=None
        ):
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

    assert (
        stub.llm_calls
    ), "Expected LLM telemetry to capture expedition manifesto enhancement"
    call = stub.llm_calls[0]
    assert call["press_type"] == "research_manifesto"
    assert call["success"] is True
    assert call["persona"] == "sarah"
    assert call["error"] is None


def test_qdrant_related_press_context(monkeypatch, tmp_path):
    monkeypatch.setenv("GREAT_WORK_QDRANT_INDEXING", "true")

    class StubManager:
        def search(self, query: str, limit: int = 5):
            return [
                {
                    "payload": {
                        "title": "Older Discovery",
                        "content": "Scholars uncovered similar artifacts in the bronze archives.",
                        "metadata": {"timestamp": "2025-05-01T12:00:00Z"},
                    }
                }
            ]

    class StubTelemetry:
        def track_llm_activity(self, *args, **kwargs):
            return None

        def track_system_event(self, *args, **kwargs):
            return None

    captured_context: Dict[str, Any] = {}

    def fake_enhance_press_release_sync(
        press_type, base_body, context, persona_name, persona_traits
    ):
        captured_context.update(context)
        return "Enhanced body"

    monkeypatch.setattr("great_work.service.get_telemetry", lambda: StubTelemetry())
    monkeypatch.setattr(
        "great_work.service.enhance_press_release_sync", fake_enhance_press_release_sync
    )
    monkeypatch.setattr(GameService, "_get_qdrant_manager", lambda self: StubManager())

    db_path = tmp_path / "state.sqlite"
    service = GameService(db_path=db_path, auto_seed=False)

    press = PressRelease(
        type="academic_gossip",
        headline="Breakthrough Announced",
        body="New findings emerge.",
        metadata={},
    )

    result = service._enhance_press_release(
        press,
        base_body="New findings emerge.",
        persona_name=None,
        persona_traits=None,
        extra_context=None,
    )

    assert result.body == "Enhanced body"
    related = captured_context.get("related_press")
    assert related and any("Older Discovery" in item for item in related)


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

    queued_press = service.state.list_queued_press()
    recruitment_layers = [
        payload
        for _, _, payload in queued_press
        if payload.get("metadata", {}).get("scheduled", {}).get("event_type")
        == "recruitment"
    ]
    assert recruitment_layers, "expected layered recruitment follow-ups to be queued"
    assert any(
        payload.get("metadata", {}).get("scheduled", {}).get("layer_type")
        in {"academic_gossip", "recruitment_followup"}
        for payload in recruitment_layers
    )

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
    assert "relationship_modifier" in notice.metadata
    assert "relationship_modifier" in second_notice.metadata
    assert notice.metadata["llm"]["persona"] == "Dr Elara Ironquill"
    assert second_notice.metadata["llm"]["persona"] == "Dr Elara Ironquill"

    queued = service.state.list_queued_press()
    assert queued, "Expected defection follow-ups to be scheduled"
    scheduled_followups = service.release_scheduled_press(
        datetime.now(timezone.utc) + timedelta(hours=4)
    )
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


def test_defection_probability_respects_relationship(tmp_path, monkeypatch):
    positive_root = tmp_path / "positive"
    positive_root.mkdir()
    service = build_service(positive_root)
    scholar_id = "s.ironquill"
    scholar = service.state.get_scholar(scholar_id)
    assert scholar is not None
    employer = scholar.contract.get("employer")
    assert employer

    scholar.memory.adjust_feeling(employer, 10.0)
    service.state.save_scholar(scholar)
    monkeypatch.setattr(service._rng, "uniform", lambda *_: 1.0)

    _, positive_notice = service.evaluate_defection_offer(
        scholar_id=scholar_id,
        offer_quality=0.4,
        mistreatment=0.1,
        alignment=0.2,
        plateau=0.2,
        new_faction="Industry",
    )

    positive_prob = positive_notice.metadata["probability"]
    positive_modifier = positive_notice.metadata["relationship_modifier"]
    assert positive_modifier < 0

    negative_root = tmp_path / "negative"
    negative_root.mkdir()
    service_cold = build_service(negative_root)
    scholar_cold = service_cold.state.get_scholar(scholar_id)
    assert scholar_cold is not None
    employer_cold = scholar_cold.contract.get("employer")
    assert employer_cold

    scholar_cold.memory.adjust_feeling(employer_cold, -10.0)
    service_cold.state.save_scholar(scholar_cold)
    monkeypatch.setattr(service_cold._rng, "uniform", lambda *_: 1.0)

    _, negative_notice = service_cold.evaluate_defection_offer(
        scholar_id=scholar_id,
        offer_quality=0.4,
        mistreatment=0.1,
        alignment=0.2,
        plateau=0.2,
        new_faction="Industry",
    )

    negative_prob = negative_notice.metadata["probability"]
    negative_modifier = negative_notice.metadata["relationship_modifier"]
    assert negative_modifier > 0
    assert negative_prob > positive_prob


def test_evaluate_scholar_offer_relationship_bonus(tmp_path):
    offer_root = tmp_path / "offer-rel"
    offer_root.mkdir()
    service = build_service(offer_root)
    service.ensure_player("poacher", "Poacher")

    scholar_id = "s.ironquill"
    scholar = service.state.get_scholar(scholar_id)
    assert scholar is not None
    employer = scholar.contract.get("employer")
    assert employer

    scholar.memory.feelings.clear()
    scholar.contract["mentorship_history"] = []
    scholar.contract["sidecast_history"] = []
    service.state.save_scholar(scholar)

    offer = OfferRecord(
        scholar_id=scholar_id,
        faction="Industry",
        rival_id="poacher",
        patron_id=employer,
        offer_type="initial",
        influence_offered={"industry": 10},
        terms={},
        status="pending",
    )
    offer_id = service.state.save_offer(offer)

    base_prob = service.evaluate_scholar_offer(offer_id)

    scholar = service.state.get_scholar(scholar_id)
    assert scholar is not None
    scholar.contract["mentorship_history"] = [
        {
            "event": "completion",
            "mentor_id": "poacher",
            "mentor": "Poacher",
            "track": "Industry",
            "timestamp": "2025-09-25T12:00:00+00:00",
        }
    ]
    service.state.save_scholar(scholar)

    boosted_prob = service.evaluate_scholar_offer(offer_id)
    assert boosted_prob > base_prob

    scholar = service.state.get_scholar(scholar_id)
    assert scholar is not None
    scholar.contract.setdefault("mentorship_history", []).append(
        {
            "event": "completion",
            "mentor_id": employer,
            "mentor": employer,
            "track": "Academia",
            "timestamp": "2025-09-26T12:00:00+00:00",
        }
    )
    service.state.save_scholar(scholar)

    reduced_prob = service.evaluate_scholar_offer(offer_id)
    assert reduced_prob < boosted_prob


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
        == service.settings.confidence_wagers[ConfidenceLevel.STAKE_CAREER.value][
            "penalty"
        ]
    )
    assert (
        reference["wagers"][ConfidenceLevel.STAKE_CAREER.value][
            "triggers_recruitment_cooldown"
        ]
        is True
    )

    thresholds = reference["action_thresholds"]
    assert (
        thresholds["recruitment"] == service.settings.action_thresholds["recruitment"]
    )

    bounds = reference["reputation_bounds"]
    assert bounds["min"] == service.settings.reputation_bounds["min"]
    assert bounds["max"] == service.settings.reputation_bounds["max"]


def test_create_offer_includes_relationship_snapshot(tmp_path):
    service = build_service(tmp_path)
    service.ensure_player("poacher", "Poacher")

    scholar = service.state.get_scholar("s.ironquill")
    assert scholar is not None
    patron_id = scholar.contract.get("employer")
    if not patron_id:
        patron_id = "Archivist"
        scholar.contract["employer"] = patron_id
        service.state.save_scholar(scholar)
    service.ensure_player(patron_id, patron_id)

    rival = service.state.get_player("poacher")
    rival.influence["industry"] = 5
    service.state.upsert_player(rival)

    offer_id, press = service.create_defection_offer(
        scholar_id=scholar.id,
        rival_id="poacher",
        target_faction="Industry",
        influence_offer={"industry": 3},
    )

    assert press
    body = press[0].body
    assert "Loyalty snapshot" in body
    meta_snapshot = press[0].metadata.get("relationship_snapshot")
    assert meta_snapshot
    assert meta_snapshot["rival"]["display_name"] == "Poacher"

    stored_offer = service.state.get_offer(offer_id)
    assert stored_offer is not None
    assert (
        stored_offer.relationship_snapshot.get("rival", {}).get("feeling") is not None
    )


def test_counter_offer_carries_relationship_snapshot(tmp_path):
    service = build_service(tmp_path)
    service.ensure_player("poacher", "Poacher")

    scholar = service.state.get_scholar("s.ironquill")
    assert scholar is not None
    patron_id = scholar.contract.get("employer")
    if not patron_id:
        patron_id = "Archivist"
        scholar.contract["employer"] = patron_id
        service.state.save_scholar(scholar)
    service.ensure_player(patron_id, patron_id)

    rival = service.state.get_player("poacher")
    rival.influence.update({"industry": 5})
    service.state.upsert_player(rival)

    offer_id, _ = service.create_defection_offer(
        scholar_id=scholar.id,
        rival_id="poacher",
        target_faction="Industry",
        influence_offer={"industry": 3},
    )

    patron = service.state.get_player(patron_id)
    patron.influence.update({"industry": 4})
    service.state.upsert_player(patron)

    counter_id, press = service.counter_offer(
        player_id=patron_id,
        original_offer_id=offer_id,
        counter_influence={"industry": 2},
    )

    assert counter_id
    assert press
    assert "Loyalty snapshot" in press[0].body
    snapshot = press[0].metadata.get("relationship_snapshot")
    assert snapshot
    assert snapshot["patron"]["display_name"] == patron.display_name
