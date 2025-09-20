"""High-level game service orchestrating commands."""
from __future__ import annotations

import logging
import os
import random
import time
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import threading

from .config import Settings, get_settings
from .expeditions import ExpeditionResolver, FailureTables
from .models import (
    ConfidenceLevel,
    Event,
    ExpeditionOutcome,
    ExpeditionPreparation,
    ExpeditionRecord,
    MemoryFact,
    OfferRecord,
    Player,
    Scholar,
    PressRecord,
    PressRelease,
    SidewaysEffectType,
    TheoryRecord,
)
from .press import (
    BulletinContext,
    GossipContext,
    OutcomeContext,
    ExpeditionContext,
    RecruitmentContext,
    DefectionContext,
    SeasonalCommitmentContext,
    FactionProjectUpdateContext,
    FactionInvestmentContext,
    ArchiveEndowmentContext,
    academic_bulletin,
    academic_gossip,
    defection_notice,
    discovery_report,
    recruitment_report,
    retraction_notice,
    research_manifesto,
    seasonal_commitment_update,
    seasonal_commitment_complete,
    faction_project_update,
    faction_project_complete,
    faction_investment,
    archive_endowment,
)
from .multi_press import MultiPressGenerator
from .rng import DeterministicRNG
from .scholars import ScholarRepository, apply_scar, defection_probability
from .state import GameState
from .telemetry import get_telemetry
from .llm_client import enhance_press_release_sync, LLMGenerationError, LLMNotEnabledError
from .press_tone import get_tone_seed


logger = logging.getLogger(__name__)


_DEFAULT_SYMPOSIUM_TOPICS: List[Tuple[str, str]] = [
    (
        "The Nature of Truth",
        "Does objective truth exist in scientific inquiry, or is all knowledge relative to the observer?",
    ),
    (
        "Ethics of Discovery",
        "Should there be limits on what knowledge humanity pursues?",
    ),
    (
        "Collaboration vs Competition",
        "Does competition or collaboration lead to greater scientific advancement?",
    ),
    (
        "The Role of Intuition",
        "What place does intuition have in rigorous academic work?",
    ),
    (
        "Funding Priorities",
        "Should research funding favor practical applications or pure discovery?",
    ),
    (
        "The Great Work Itself",
        "What is the true purpose of our collective academic endeavor?",
    ),
    (
        "Knowledge Ownership",
        "Can ideas truly be owned, or does all knowledge belong to humanity?",
    ),
    (
        "Academic Hierarchy",
        "Do traditional academic structures help or hinder progress?",
    ),
]


@dataclass
class ExpeditionOrder:
    code: str
    player_id: str
    expedition_type: str
    objective: str
    team: List[str]
    funding: List[str]
    preparation: ExpeditionPreparation
    prep_depth: str
    confidence: ConfidenceLevel
    timestamp: datetime


class GameService:
    """Coordinates between state, RNG and generators."""

    class GamePausedError(RuntimeError):
        """Raised when the game is paused and actions are disallowed."""

    _MIN_SCHOLAR_ROSTER = 20
    _MAX_SCHOLAR_ROSTER = 30
    _EXPEDITION_COSTS: Dict[str, Dict[str, int]] = {
        "think_tank": {"academia": 1},
        "field": {"academia": 1, "government": 1},
        "great_project": {"academia": 2, "government": 2, "industry": 2},
    }

    _EXPEDITION_REWARDS: Dict[str, Dict[str, int]] = {
        "think_tank": {"academia": 1},
        "field": {"government": 1, "industry": 1},
        "great_project": {"academia": 2, "industry": 2, "foreign": 1},
    }
    _FACTIONS: Tuple[str, ...] = ("academia", "government", "industry", "religion", "foreign")

    _CAREER_TRACKS: Dict[str, List[str]] = {
        "Academia": ["Postdoc", "Fellow", "Professor"],
        "Industry": ["Associate", "Director", "Visionary"],
    }
    _CAREER_TICKS_REQUIRED = 3
    _FOLLOWUP_DELAYS: Dict[str, timedelta] = {
        "defection_grudge": timedelta(days=2),
        "defection_return": timedelta(days=3),
        "recruitment_grudge": timedelta(days=1),
    }

    def __init__(
        self,
        db_path: Path,
        settings: Settings | None = None,
        repository: ScholarRepository | None = None,
        failure_tables: FailureTables | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or ScholarRepository()
        self.state = GameState(
            db_path,
            repository=self.repository,
            start_year=self.settings.timeline_start_year,
            admin_notifier=self._queue_admin_notification,
        )
        self.resolver = ExpeditionResolver(failure_tables or FailureTables())
        self._rng = DeterministicRNG(seed=42)
        self._pending_expeditions: Dict[str, ExpeditionOrder] = {}
        self._generated_counter = self._initial_generated_counter()
        tone_setting = os.getenv("GREAT_WORK_PRESS_SETTING")
        self._multi_press = MultiPressGenerator(setting=tone_setting)
        self._llm_lock = threading.Lock()
        self._llm_fail_start: Optional[datetime] = None
        self._llm_pause_timeout = float(os.getenv("LLM_PAUSE_TIMEOUT", "600"))
        self._paused = False
        self._pause_reason: Optional[str] = None
        self._pause_source: Optional[str] = None
        self._admin_notifications: deque[str] = deque()
        self._telemetry = get_telemetry()
        self._latest_symposium_scoring: List[Dict[str, object]] = []
        if not any(True for _ in self.state.all_scholars()):
            self.state.seed_base_scholars()
        self._ensure_roster()

    def is_paused(self) -> bool:
        return self._paused

    def pause_reason(self) -> Optional[str]:
        return self._pause_reason

    def drain_admin_notifications(self) -> List[str]:
        messages = list(self._admin_notifications)
        self._admin_notifications.clear()
        return messages

    def push_admin_notification(self, message: str) -> None:
        self._queue_admin_notification(message)

    def _queue_admin_notification(self, message: str) -> None:
        logger.warning(message)
        self._admin_notifications.append(message)

    def release_scheduled_press(self, now: Optional[datetime] = None) -> List[PressRelease]:
        """Release any scheduled press items that are due as of ``now``."""

        now = now or datetime.now(timezone.utc)
        due = self.state.due_queued_press(now)
        if not due:
            return []

        releases: List[PressRelease] = []
        for queue_id, release_at, payload in due:
            release = PressRelease(
                type=payload.get("type", "scheduled_press"),
                headline=payload.get("headline", "Scheduled Update"),
                body=payload.get("body", ""),
                metadata=payload.get("metadata", {}),
            )
            release.metadata.setdefault("scheduled", {})
            release.metadata["scheduled"].update(
                {
                    "release_at": release_at.isoformat(),
                }
            )
            self._archive_press(release, now)
            self.state.clear_queued_press(queue_id)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="scheduled_press_released",
                    payload={
                        "headline": release.headline,
                        "release_at": release_at.isoformat(),
                    },
                )
            )
            releases.append(release)
        return releases

    def pending_press_count(self) -> int:
        """Return the number of scheduled press items waiting to release."""

        return self.state.count_queued_press()

    def upcoming_press(
        self,
        *,
        limit: int = 5,
        within_hours: int = 48,
    ) -> List[Dict[str, object]]:
        """Provide a snapshot of scheduled press due within the time horizon."""

        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=within_hours)
        upcoming: List[Dict[str, object]] = []
        for _, release_at, payload in self.state.list_queued_press():
            if release_at > horizon:
                continue
            metadata = payload.get("metadata", {}) or {}
            badges = self._press_badges(metadata)
            upcoming.append(
                {
                    "headline": payload.get("headline", "Scheduled Update"),
                    "type": payload.get("type", "scheduled_press"),
                    "release_at": release_at,
                    "metadata": metadata,
                    "badges": badges,
                }
            )
        upcoming.sort(key=lambda item: item["release_at"])
        return upcoming[:limit]

    def create_digest_highlights(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 5,
        within_hours: int = 24,
    ) -> Optional[PressRelease]:
        """Create a digest highlight press release summarising upcoming drops."""

        now = now or datetime.now(timezone.utc)
        horizon = now + timedelta(hours=within_hours)
        items: List[Dict[str, object]] = []
        for _, release_at, payload in self.state.list_queued_press():
            if release_at > horizon:
                continue
            items.append(
                {
                    "headline": payload.get("headline", "Scheduled Update"),
                    "type": payload.get("type", "scheduled_press"),
                    "metadata": payload.get("metadata", {}) or {},
                    "release_at": release_at,
                }
            )

        if not items:
            return None

        items.sort(key=lambda item: item["release_at"])
        items = items[:limit]
        tone_seed = get_tone_seed("digest_highlight", getattr(self._multi_press, "setting", None))
        headline_template = None
        callout = None
        blurb_template = None
        if tone_seed:
            headline_template = tone_seed.get("headline")
            callout = tone_seed.get("callout")
            blurb_template = tone_seed.get("blurb_template")
        headline = headline_template.format(count=len(items)) if headline_template else f"Upcoming Highlights ({len(items)})"

        lines: List[str] = []
        metadata_items: List[Dict[str, object]] = []
        for item in items:
            release_at = item["release_at"]
            delta_minutes = max(0, int((release_at - now).total_seconds() // 60))
            if delta_minutes >= 60:
                hours = delta_minutes // 60
                minutes = delta_minutes % 60
                relative = f"{hours}h {minutes}m"
            else:
                relative = f"{delta_minutes}m"
            absolute = release_at.strftime("%Y-%m-%d %H:%M UTC")
            metadata = item.get("metadata", {})
            badges = self._press_badges(metadata)
            label_prefix = f"[{" | ".join(badges)}] " if badges else ""
            summary = f"{item['headline']} — {absolute} (in {relative})"
            if blurb_template:
                blurb = blurb_template.format(
                    headline=item["headline"],
                    relative_time=relative,
                    call_to_action=callout or ""
                )
            else:
                blurb = summary
            if label_prefix:
                blurb = f"{label_prefix}{blurb}"
            lines.append(f"• {blurb}")
            metadata_items.append(
                {
                    "headline": item["headline"],
                    "type": item["type"],
                    "release_at": release_at.isoformat(),
                    "relative_minutes": delta_minutes,
                    "badges": badges,
                    "source": metadata.get("source"),
                }
            )

        if callout:
            lines.append(callout)

        base_body = "\n".join(lines)
        release = PressRelease(
            type="digest_highlights",
            headline=headline,
            body=base_body,
            metadata={
                "digest_highlights": {
                    "generated_at": now.isoformat(),
                    "horizon_hours": within_hours,
                    "items": metadata_items,
                }
            },
        )
        if tone_seed:
            release.metadata.setdefault("tone_seed", {}).update(tone_seed)
        extra_context: Dict[str, object] = {
            "event_type": "digest_highlight",
            "item_count": len(items),
            "tone_seed": tone_seed or {},
        }
        release = self._enhance_press_release(
            release,
            base_body=base_body,
            persona_name=None,
            persona_traits=None,
            extra_context=extra_context,
        )
        self._archive_press(release, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="digest_highlights_generated",
                payload={
                    "headline": release.headline,
                    "item_count": len(items),
                },
            )
        )
        return release

    @staticmethod
    def _press_badges(metadata: Dict[str, object]) -> List[str]:
        """Derive descriptive badges for scheduled press metadata."""

        if not isinstance(metadata, dict):
            return []
        badges: List[str] = []
        source = metadata.get("source")
        if source == "sideways_followup":
            badges.append("Follow-Up")
        tags = metadata.get("tags")
        if isinstance(tags, (list, tuple)):
            badges.extend(str(tag) for tag in tags if tag)
        elif isinstance(tags, str) and tags:
            badges.append(tags)
        return badges

    def _ensure_not_paused(self) -> None:
        if self._paused:
            raise GameService.GamePausedError(self._pause_reason or "Game is paused")

    def _register_llm_failure(self) -> bool:
        now = datetime.now(timezone.utc)
        with self._llm_lock:
            if self._llm_fail_start is None:
                self._llm_fail_start = now
            elapsed = (now - self._llm_fail_start).total_seconds()
            return elapsed >= self._llm_pause_timeout

    def _clear_llm_failure(self) -> None:
        with self._llm_lock:
            self._llm_fail_start = None

    def _pause_for_llm(self, reason: str) -> None:
        with self._llm_lock:
            if self._paused:
                return
            self._paused = True
            self._pause_reason = f"Narrative generator unavailable: {reason}"
            self._pause_source = "llm"
        self._queue_admin_notification(
            f"⚠️ Game paused — {self._pause_reason}"
        )
        now = datetime.now(timezone.utc)
        pause_press = PressRelease(
            type="admin_action",
            headline="Game Pause",
            body=f"Live actions are halted while narrative systems recover: {reason}.",
            metadata={
                "source": "llm",
                "reason": reason,
            },
        )
        self._archive_press(pause_press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="game_paused",
                payload={
                    "reason": reason,
                    "source": "llm",
                },
            )
        )
        layers = self._multi_press.generate_admin_layers(
            event="pause",
            actor="Operations Council",
            reason=reason,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={pause_press.type},
            timestamp=now,
            event_type="admin",
        )
        try:
            self._telemetry.track_system_event(
                "llm_pause",
                source="llm",
                reason=reason,
            )
        except Exception:
            logger.debug("Telemetry tracking for llm_pause failed", exc_info=True)

    def _resume_from_llm(self) -> None:
        with self._llm_lock:
            if not self._paused or self._pause_source != "llm":
                self._llm_fail_start = None
                return
            previous_reason = self._pause_reason
            self._paused = False
            self._pause_reason = None
            self._pause_source = None
            self._llm_fail_start = None
        self._queue_admin_notification("✅ Narrative generator restored — game resumed.")
        now = datetime.now(timezone.utc)
        resume_press = PressRelease(
            type="admin_action",
            headline="Game Resume",
            body="Narrative systems restored; queued actions will resume shortly.",
            metadata={
                "source": "llm",
                "reason": previous_reason,
            },
        )
        self._archive_press(resume_press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="game_resumed",
                payload={
                    "source": "llm",
                    "reason": previous_reason,
                },
            )
        )
        layers = self._multi_press.generate_admin_layers(
            event="resume",
            actor="Operations Council",
            reason=previous_reason,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={resume_press.type},
            timestamp=now,
            event_type="admin",
        )
        try:
            self._telemetry.track_system_event(
                "llm_resume",
                source="llm",
                reason=previous_reason,
            )
        except Exception:
            logger.debug("Telemetry tracking for llm_resume failed", exc_info=True)

    def _resolve_scholar_traits(self, scholar_name: str | None) -> Optional[Dict[str, object]]:
        if not scholar_name:
            return None
        for scholar in self.state.all_scholars():
            if scholar.name.lower() == scholar_name.lower():
                return {
                    "personality": scholar.archetype,
                    "specialization": ", ".join(scholar.disciplines) or "general research",
                    "quirks": scholar.methods,
                    "drives": scholar.drives,
                }
        return None

    def _enhance_press_release(
        self,
        release: PressRelease,
        *,
        base_body: str,
        persona_name: Optional[str] = None,
        persona_traits: Optional[Dict[str, object]] = None,
        extra_context: Optional[Dict[str, object]] = None,
    ) -> PressRelease:
        allowed_while_paused = {
            "admin_action",
            "admin_update",
            "symposium_reminder",
        }
        event_type = (extra_context or {}).get("event_type") if extra_context else None
        if (
            self._paused
            and release.type not in allowed_while_paused
            and event_type != "admin"
        ):
            raise GameService.GamePausedError(self._pause_reason or "Game is paused")
        telemetry = getattr(self, "_telemetry", None)
        if telemetry is None:
            telemetry = get_telemetry()
            self._telemetry = telemetry
        start_time = time.perf_counter()
        context_payload: Dict[str, object] = {
            "type": release.type,
            "headline": release.headline,
            "body": base_body,
        }
        if extra_context:
            context_payload.update(extra_context)
        try:
            enhanced_body = enhance_press_release_sync(
                release.type,
                base_body,
                context_payload,
                persona_name,
                persona_traits,
            )
            self._clear_llm_failure()
            self._resume_from_llm()
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                telemetry.track_llm_activity(
                    release.type,
                    success=True,
                    duration_ms=duration_ms,
                    persona=persona_name,
                )
            except Exception:
                logger.debug("Telemetry tracking for LLM success failed", exc_info=True)
        except (LLMGenerationError, LLMNotEnabledError) as exc:
            logger.warning("LLM enhancement failed for %s: %s", release.type, exc)
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                telemetry.track_llm_activity(
                    release.type,
                    success=False,
                    duration_ms=duration_ms,
                    persona=persona_name,
                    error=str(exc),
                )
            except Exception:
                logger.debug("Telemetry tracking for LLM failure failed", exc_info=True)
            if self._register_llm_failure():
                self._pause_for_llm(str(exc))
            return release

        release.body = enhanced_body
        metadata = dict(release.metadata)
        metadata.setdefault("llm", {})
        metadata["llm"].update(
            {
                "persona": persona_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        release.metadata = metadata
        return release

    # Player helpers ----------------------------------------------------
    def ensure_player(self, player_id: str, display_name: Optional[str] = None) -> None:
        player = self.state.get_player(player_id)
        if player:
            self._ensure_influence_structure(player)
            self.state.upsert_player(player)
            return
        display = display_name or player_id
        self.state.upsert_player(
            player=Player(
                id=player_id,
                display_name=display,
                reputation=0,
                influence={faction: 0 for faction in self._FACTIONS},
            )
        )

    def submit_theory(
        self,
        player_id: str,
        theory: str,
        confidence: ConfidenceLevel,
        supporters: List[str],
        deadline: str,
    ) -> PressRelease:
        self._ensure_not_paused()
        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        assert player is not None
        ctx = BulletinContext(
            bulletin_number=len(self.state.export_events()) + 1,
            player=player_id,
            theory=theory,
            confidence=confidence.value,
            supporters=supporters,
            deadline=deadline,
        )
        press = academic_bulletin(ctx)
        base_body = press.body
        press.metadata = {
            **press.metadata,
            "submission": {
                "player_id": player_id,
                "display_name": player.display_name,
                "theory": theory,
                "confidence": confidence.value,
                "supporters": list(supporters),
                "deadline": deadline,
            },
        }
        press = self._enhance_press_release(
            press,
            base_body=base_body,
            persona_name=player.display_name,
            persona_traits=None,
            extra_context={
                "type": "academic_bulletin",
                "player": player.display_name,
                "action": (
                    f"submitted '{theory}' with {confidence.value} confidence; "
                    f"counter-claims invited before {deadline}"
                ),
                "theory": theory,
                "confidence": confidence.value,
                "supporters": supporters,
                "deadline": deadline,
            },
        )
        now = datetime.now(timezone.utc)
        self.state.append_event(
            Event(
                timestamp=now,
                action="submit_theory",
                payload={
                    "player": player_id,
                    "theory": theory,
                    "confidence": confidence.value,
                    "supporters": supporters,
                    "deadline": deadline,
                },
            )
        )
        self.state.record_theory(
            TheoryRecord(
                timestamp=now,
                player_id=player_id,
                theory=theory,
                confidence=confidence.value,
                supporters=supporters,
                deadline=deadline,
            )
        )
        self._archive_press(press, now)
        return press

    def post_table_talk(
        self,
        player_id: str,
        display_name: str,
        message: str,
    ) -> PressRelease:
        """Publish a table-talk message with LLM enhancement and archival."""

        self._ensure_not_paused()
        self.ensure_player(player_id, display_name)
        player = self.state.get_player(player_id)
        assert player is not None

        now = datetime.now(timezone.utc)
        headline = f"Table Talk — {player.display_name}"
        base_body = f"{player.display_name}: {message}"
        press = PressRelease(
            type="table_talk",
            headline=headline,
            body=base_body,
            metadata={
                "table_talk": {
                    "player_id": player_id,
                    "display_name": player.display_name,
                    "message": message,
                    "posted_at": now.isoformat(),
                }
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=base_body,
            persona_name=player.display_name,
            persona_traits=None,
            extra_context={
                "type": "table_talk",
                "player": player.display_name,
                "action": f"shared table-talk: {message}",
                "message": message,
            },
        )
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="table_talk_post",
                payload={
                    "player": player_id,
                    "display_name": player.display_name,
                    "message": message,
                },
            )
        )
        table_layers = self._multi_press.generate_table_talk_layers(
            speaker=player.display_name,
            message=message,
            scholars=list(self.state.all_scholars()),
        )
        self._apply_multi_press_layers(
            table_layers,
            skip_types={press.type},
            timestamp=now,
            event_type="table_talk",
        )
        return press

    def queue_expedition(
        self,
        code: str,
        player_id: str,
        expedition_type: str,
        objective: str,
        team: List[str],
        funding: List[str],
        preparation: ExpeditionPreparation,
        prep_depth: str,
        confidence: ConfidenceLevel,
    ) -> PressRelease:
        self._ensure_not_paused()
        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        assert player is not None
        self._require_reputation(player, f"expedition_{expedition_type}")
        self._apply_expedition_costs(player, expedition_type, funding)
        self.state.upsert_player(player)
        order = ExpeditionOrder(
            code=code,
            player_id=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
            preparation=preparation,
            prep_depth=prep_depth,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
        )
        self._pending_expeditions[code] = order
        record = ExpeditionRecord(
            code=code,
            player_id=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
            prep_depth=prep_depth,
            confidence=confidence.value,
            timestamp=order.timestamp,
        )
        self.state.record_expedition(record)
        self.state.append_event(
            Event(
                timestamp=order.timestamp,
                action="launch_expedition",
                payload={
                    "code": code,
                    "player": player_id,
                    "type": expedition_type,
                    "objective": objective,
                    "team": team,
                    "funding": funding,
                    "prep_depth": prep_depth,
                    "confidence": confidence.value,
                },
            )
        )
        ctx = ExpeditionContext(
            code=code,
            player=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding,
        )
        press = research_manifesto(ctx)
        base_body = press.body
        persona_name = player.display_name
        persona_traits = None
        context_payload = {
            "player": persona_name,
            "expedition_code": code,
            "objective": objective,
            "expedition_type": expedition_type,
        }
        press = self._enhance_press_release(
            press,
            base_body=base_body,
            persona_name=persona_name,
            persona_traits=persona_traits,
            extra_context=context_payload,
        )
        self._archive_press(press, order.timestamp)
        return press

    def launch_expedition(
        self,
        player_id: str,
        expedition_type: str,
        objective: str,
        team: List[str],
        funding: Dict[str, int],
        confidence: ConfidenceLevel,
        prep_depth: str = "standard",
    ) -> PressRelease:
        """Simplified expedition launching for tests and external callers.

        This is a convenience wrapper around queue_expedition that handles
        parameter conversion and code generation.
        """
        # Generate expedition code using timestamp for uniqueness
        import time
        timestamp_part = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
        code = f"{expedition_type.upper()[:2]}-{timestamp_part}"

        # Convert funding dict to list
        funding_list = []
        for faction, amount in funding.items():
            for _ in range(amount):
                funding_list.append(faction)

        # Create minimal preparation with zero bonuses
        preparation = ExpeditionPreparation(
            think_tank_bonus=0,
            expertise_bonus=0,
            site_friction=0,
            political_friction=0
        )

        # Queue the expedition
        return self.queue_expedition(
            code=code,
            player_id=player_id,
            expedition_type=expedition_type,
            objective=objective,
            team=team,
            funding=funding_list,
            preparation=preparation,
            prep_depth=prep_depth,
            confidence=confidence,
        )

    def resolve_expeditions(self) -> List[PressRelease]:
        """Alias for resolve_pending_expeditions for backward compatibility."""
        return self.resolve_pending_expeditions()

    def resolve_pending_expeditions(self) -> List[PressRelease]:
        self._ensure_not_paused()
        releases: List[PressRelease] = []
        releases.extend(self.release_scheduled_press())
        for code, order in list(self._pending_expeditions.items()):
            result = self.resolver.resolve(
                self._rng, order.preparation, order.prep_depth, order.expedition_type
            )
            delta = self._confidence_delta(order.confidence, result.outcome)
            player = self.state.get_player(order.player_id)
            assert player is not None
            new_reputation = self._apply_reputation_change(player, delta, order.confidence)
            self.state.upsert_player(player)
            reactions = self._generate_reactions(order.team, result)
            ctx = OutcomeContext(
                code=code,
                player=order.player_id,
                expedition_type=order.expedition_type,
                result=result,
                reputation_change=delta,
                reactions=reactions,
            )
            if result.outcome == ExpeditionOutcome.FAILURE:
                release = retraction_notice(ctx)
            else:
                release = discovery_report(ctx)
            base_body = release.body
            persona_name = player.display_name
            context_payload = {
                "player": persona_name,
                "expedition_code": code,
                "outcome": result.outcome.value,
                "reputation_delta": delta,
            }
            release = self._enhance_press_release(
                release,
                base_body=base_body,
                persona_name=persona_name,
                persona_traits=None,
                extra_context=context_payload,
            )
            releases.append(release)
            now = datetime.now(timezone.utc)
            self._archive_press(release, now)
            expedition_ctx = ExpeditionContext(
                code=order.code,
                player=order.player_id,
                expedition_type=order.expedition_type,
                objective=order.objective,
                team=order.team,
                funding=order.funding,
            )
            depth = self._multi_press.determine_depth(
                event_type=f"expedition_{order.expedition_type}",
                reputation_change=delta,
                confidence_level=order.confidence.value,
                is_first_time=result.outcome == ExpeditionOutcome.LANDMARK,
            )
            scholars = list(self.state.all_scholars())
            layers = self._multi_press.generate_expedition_layers(
                expedition_ctx,
                ctx,
                scholars,
                depth,
            )
            extra_releases = self._apply_multi_press_layers(
                layers,
                skip_types={"research_manifesto", release.type},
                timestamp=now,
                event_type="expedition",
            )
            releases.extend(extra_releases)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="expedition_resolved",
                    payload={
                        "code": code,
                        "player": order.player_id,
                        "type": order.expedition_type,
                        "result": result.outcome.value,
                        "roll": result.roll,
                        "modifier": result.modifier,
                        "final": result.final_score,
                        "confidence": order.confidence.value,
                        "reputation_delta": delta,
                        "reputation_after": new_reputation,
                    },
                )
            )
            record = ExpeditionRecord(
                code=order.code,
                player_id=order.player_id,
                expedition_type=order.expedition_type,
                objective=order.objective,
                team=order.team,
                funding=order.funding,
                prep_depth=order.prep_depth,
                confidence=order.confidence.value,
                outcome=result.outcome.value,
                reputation_delta=delta,
                timestamp=order.timestamp,
            )
            self.state.record_expedition(
                record,
                result_payload={
                    "roll": result.roll,
                    "modifier": result.modifier,
                    "final": result.final_score,
                    "sideways": result.sideways_discovery,
                    "failure": result.failure_detail,
                },
            )
            self._apply_expedition_rewards(player, order.expedition_type, result)
            self.state.upsert_player(player)
            self._update_relationships_from_result(order, result)
            # Apply sideways discovery effects if present
            if result.sideways_effects:
                effect_releases = self._apply_sideways_effects(order, result, player)
                releases.extend(effect_releases)
            sidecast = self._maybe_spawn_sidecast(order, result)
            if sidecast:
                releases.append(sidecast)
                self._archive_press(sidecast, now)
            del self._pending_expeditions[code]
        releases.extend(self.release_scheduled_press())
        return releases

    # Public actions ----------------------------------------------------
    def attempt_recruitment(
        self,
        player_id: str,
        scholar_id: str,
        faction: str,
        base_chance: float = 0.6,
    ) -> Tuple[bool, PressRelease]:
        """Attempt to recruit a scholar, applying cooldown and influence effects."""

        self._ensure_not_paused()
        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        scholar = self.state.get_scholar(scholar_id)
        if not player or not scholar:
            raise ValueError("Unknown player or scholar")

        self._require_reputation(player, "recruitment")
        chance_payload = self._compute_recruitment_chance(
            player=player,
            faction=faction,
            base_chance=base_chance,
        )
        base_chance_value = chance_payload["chance"]
        relationship_details = self._relationship_bonus(scholar, player_id)
        chance = self._clamp_probability(base_chance_value + relationship_details["total"])
        roll = self._rng.uniform(0.0, 1.0)
        success = roll < chance
        now = datetime.now(timezone.utc)
        player.cooldowns["recruitment"] = max(2, player.cooldowns.get("recruitment", 0))

        if success:
            scholar.memory.adjust_feeling(player_id, 2.0)
            scholar.contract["employer"] = player_id
            scholar.contract["faction"] = faction
            self._apply_influence_change(player, faction, 1)
            press = recruitment_report(
                RecruitmentContext(
                    player=player_id,
                    scholar=scholar.name,
                    outcome="success",
                    chance=chance,
                    faction=faction,
                    relationship_modifier=relationship_details["total"],
                )
            )
        else:
            scholar.memory.adjust_feeling(player_id, -1.0)
            press = recruitment_report(
                RecruitmentContext(
                    player=player_id,
                    scholar=scholar.name,
                    outcome="failure",
                    chance=chance,
                    faction=faction,
                    relationship_modifier=relationship_details["total"],
                )
            )
            resolve_at = now + self._FOLLOWUP_DELAYS["recruitment_grudge"]
            self.state.schedule_followup(
                scholar_id,
                "recruitment_grudge",
                resolve_at,
                {"player": player_id, "faction": faction},
            )
        press.metadata.update(
            {
                "player": player_id,
                "scholar": scholar.id,
                "faction": faction,
                "chance": chance,
                "base_chance": base_chance_value,
                "relationship_modifier": relationship_details["total"],
                "relationship_details": relationship_details,
            }
        )
        self.state.save_scholar(scholar)
        self.state.upsert_player(player)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="recruitment_attempt",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "faction": faction,
                    "chance": chance,
                    "success": success,
                    "cooldown_penalty": chance_payload["cooldown_penalty"],
                    "influence_bonus": chance_payload["influence_bonus"],
                    "relationship": relationship_details,
                },
            )
        )
        observers = list(self.state.all_scholars())
        recruitment_layers = self._multi_press.generate_recruitment_layers(
            player=player.display_name,
            scholar=scholar,
            success=success,
            faction=faction,
            chance=chance,
            observers=observers,
        )
        self._apply_multi_press_layers(
            recruitment_layers,
            skip_types={press.type},
            timestamp=now,
            event_type="recruitment",
        )
        return success, press

    def start_seasonal_commitment(
        self,
        player_id: str,
        faction: str,
        *,
        tier: Optional[str] = None,
        base_cost: Optional[int] = None,
        duration_days: Optional[int] = None,
        allow_override: bool = False,
    ) -> int:
        now = datetime.now(timezone.utc)
        player = self.state.get_player(player_id)
        if player is None:
            raise ValueError(f"Unknown player {player_id}")
        relationship = self._player_faction_relationship(
            player,
            faction,
            weight=self.settings.seasonal_commitment_relationship_weight,
        )
        if not allow_override and relationship < self.settings.seasonal_commitment_min_relationship:
            raise ValueError(
                "Seasonal commitments require a neutral or better relationship with the faction"
            )
        base = base_cost if base_cost is not None else self.settings.seasonal_commitment_base_cost
        duration = duration_days if duration_days is not None else self.settings.seasonal_commitment_duration_days
        end_at = now + timedelta(days=duration)
        return self.state.create_seasonal_commitment(
            player_id=player_id,
            faction=faction,
            tier=tier,
            base_cost=base,
            start_at=now,
            end_at=end_at,
        )

    def list_seasonal_commitments(self, player_id: str) -> List[Dict[str, object]]:
        return self.state.list_player_commitments(player_id)

    def start_faction_project(
        self,
        name: str,
        faction: str,
        *,
        target_progress: float,
        metadata: Optional[Dict[str, object]] = None,
    ) -> int:
        return self.state.create_faction_project(
            name=name,
            faction=faction,
            target_progress=target_progress,
            metadata=metadata,
        )

    def list_faction_projects(self, *, include_completed: bool = False) -> List[Dict[str, object]]:
        return self.state.list_faction_projects(include_completed=include_completed)

    def invest_in_faction(
        self,
        player_id: str,
        faction: str,
        amount: int,
        *,
        program: Optional[str] = None,
    ) -> PressRelease:
        self._ensure_not_paused()
        if faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {faction}")
        if amount < self.settings.faction_investment_min_amount:
            raise ValueError(
                f"Minimum investment is {self.settings.faction_investment_min_amount} influence"
            )

        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        self._ensure_influence_structure(player)
        available = player.influence.get(faction, 0)
        if available < amount:
            raise ValueError(f"Not enough {faction} influence (have {available}, need {amount})")

        now = datetime.now(timezone.utc)
        self._apply_influence_change(player, faction, -amount)
        self.state.upsert_player(player)

        investment_id = self.state.record_faction_investment(
            player_id=player.id,
            faction=faction,
            amount=amount,
            program=program,
            created_at=now,
        )

        step = max(1, self.settings.faction_investment_feeling_step)
        increments = amount // step
        relationship_bonus = increments * self.settings.faction_investment_feeling_bonus
        if relationship_bonus:
            for scholar in self.state.all_scholars():
                if scholar.contract.get("employer") != player.id:
                    continue
                if faction and scholar.contract.get("faction") != faction:
                    continue
                scholar.memory.adjust_feeling(player.id, relationship_bonus)
                self.state.save_scholar(scholar)

        total_contribution = self.state.total_faction_investment(player.id, faction)

        ctx = FactionInvestmentContext(
            player=player.display_name,
            faction=faction.title(),
            amount=amount,
            total=total_contribution,
            program=program,
            relationship_bonus=relationship_bonus,
        )
        press = faction_investment(ctx)
        press.metadata.update(
            {
                "investment_id": investment_id,
                "player_id": player.id,
                "faction": faction,
                "amount": amount,
                "program": program,
                "relationship_bonus": relationship_bonus,
                "total": total_contribution,
            }
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="faction_investment",
                payload={
                    "player": player.id,
                    "faction": faction,
                    "amount": amount,
                    "program": program,
                    "total": total_contribution,
                },
            )
        )

        try:
            self._telemetry.track_game_progression(
                "faction_investment",
                float(amount),
                player_id=player.id,
                details={
                    "faction": faction,
                    "program": program,
                    "relationship_bonus": relationship_bonus,
                    "total": total_contribution,
                },
            )
        except Exception:  # pragma: no cover
            logger.debug("Failed to record faction investment telemetry", exc_info=True)

        return press

    def list_faction_investments(self, player_id: str) -> List[Dict[str, object]]:
        return self.state.list_faction_investments(player_id)

    def endow_archive(
        self,
        player_id: str,
        amount: int,
        *,
        faction: Optional[str] = None,
        program: Optional[str] = None,
    ) -> PressRelease:
        self._ensure_not_paused()
        funding_faction = faction or "academia"
        if funding_faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {funding_faction}")
        if amount < self.settings.archive_endowment_min_amount:
            raise ValueError(
                f"Minimum endowment is {self.settings.archive_endowment_min_amount} influence"
            )

        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        self._ensure_influence_structure(player)
        available = player.influence.get(funding_faction, 0)
        if available < amount:
            raise ValueError(
                f"Not enough {funding_faction} influence (have {available}, need {amount})"
            )

        now = datetime.now(timezone.utc)
        self._apply_influence_change(player, funding_faction, -amount)

        reputation_gain = 0
        threshold = self.settings.archive_endowment_reputation_threshold
        if threshold > 0:
            reputation_gain = (amount // threshold) * self.settings.archive_endowment_reputation_bonus
        if reputation_gain:
            player.adjust_reputation(
                reputation_gain,
                self.settings.reputation_bounds["min"],
                self.settings.reputation_bounds["max"],
            )
        self.state.upsert_player(player)

        endowment_id = self.state.record_archive_endowment(
            player_id=player.id,
            faction=funding_faction,
            amount=amount,
            program=program,
            created_at=now,
        )

        paid_debt = self.state.apply_influence_debt_payment(
            player_id=player.id,
            faction=funding_faction,
            amount=amount,
            now=now,
            source="symposium",
        )
        remaining = amount - paid_debt
        if remaining > 0:
            paid_debt += self.state.apply_influence_debt_payment(
                player_id=player.id,
                faction=funding_faction,
                amount=remaining,
                now=now,
                source="seasonal",
            )

        ctx = ArchiveEndowmentContext(
            player=player.display_name,
            faction=funding_faction.title(),
            amount=amount,
            program=program,
            paid_debt=paid_debt,
            reputation_delta=reputation_gain,
        )
        press = archive_endowment(ctx)
        press.metadata.update(
            {
                "endowment_id": endowment_id,
                "player_id": player.id,
                "faction": funding_faction,
                "amount": amount,
                "program": program,
                "paid_debt": paid_debt,
                "reputation_gain": reputation_gain,
            }
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="archive_endowment",
                payload={
                    "player": player.id,
                    "faction": funding_faction,
                    "amount": amount,
                    "program": program,
                    "paid_debt": paid_debt,
                    "reputation_gain": reputation_gain,
                },
            )
        )

        try:
            self._telemetry.track_game_progression(
                "archive_endowment",
                float(amount),
                player_id=player.id,
                details={
                    "faction": funding_faction,
                    "program": program,
                    "paid_debt": paid_debt,
                    "reputation_gain": reputation_gain,
                },
            )
        except Exception:  # pragma: no cover
            logger.debug("Failed to record archive endowment telemetry", exc_info=True)

        return press

    def list_archive_endowments(self, player_id: str) -> List[Dict[str, object]]:
        return self.state.list_archive_endowments(player_id)

    def recruitment_odds(
        self,
        player_id: str,
        scholar_id: str,
        base_chance: float = 0.6,
    ) -> List[Dict[str, object]]:
        """Return recruitment odds per faction without mutating state."""

        self._ensure_not_paused()
        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        scholar = self.state.get_scholar(scholar_id)
        if not player or not scholar:
            raise ValueError("Unknown player or scholar")

        self._require_reputation(player, "recruitment")

        odds: List[Dict[str, object]] = []
        relationship_details = self._relationship_bonus(scholar, player_id)
        for faction in self._FACTIONS:
            data = self._compute_recruitment_chance(
                player=player,
                faction=faction,
                base_chance=base_chance,
            )
            final_chance = self._clamp_probability(data["chance"] + relationship_details["total"])
            odds.append(
                {
                    "faction": faction,
                    "chance": final_chance,
                    "base_chance": data["chance"],
                    "influence_bonus": data["influence_bonus"],
                    "cooldown_penalty": data["cooldown_penalty"],
                    "cooldown_active": data["cooldown_active"],
                    "cooldown_remaining": data["cooldown_remaining"],
                    "influence": data["influence"],
                    "relationship_modifier": relationship_details["total"],
                }
            )
        odds.sort(key=lambda item: item["chance"], reverse=True)
        return odds

    def _compute_recruitment_chance(
        self,
        *,
        player: Player,
        faction: str,
        base_chance: float,
    ) -> Dict[str, float | int | bool]:
        """Calculate recruitment odds modifiers for the given faction."""

        raw_influence = player.influence.get(faction, 0)
        influence_bonus = max(0, raw_influence) * 0.05
        cooldown_remaining = int(player.cooldowns.get("recruitment", 0) or 0)
        cooldown_penalty = 0.5 if cooldown_remaining else 1.0
        chance = max(0.05, min(0.95, base_chance * cooldown_penalty + influence_bonus))
        return {
            "chance": chance,
            "influence_bonus": influence_bonus,
            "cooldown_penalty": cooldown_penalty,
            "cooldown_active": bool(cooldown_remaining),
            "cooldown_remaining": cooldown_remaining,
            "influence": raw_influence,
        }

    def evaluate_defection_offer(
        self,
        scholar_id: str,
        offer_quality: float,
        mistreatment: float,
        alignment: float,
        plateau: float,
        new_faction: str,
    ) -> Tuple[bool, PressRelease]:
        """Resolve a public defection offer and archive the resulting press."""

        self._ensure_not_paused()
        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError("Unknown scholar")

        relationship = self._relationship_bonus(scholar, scholar.contract.get("employer", "") or "")
        relationship_effect = -relationship["total"]
        probability = defection_probability(scholar, offer_quality, mistreatment, alignment, plateau)
        probability = self._clamp_probability(probability + relationship_effect)
        roll = self._rng.uniform(0.0, 1.0)
        timestamp = datetime.now(timezone.utc)
        former_employer = scholar.contract.get("employer", "their patron")
        if roll < probability:
            apply_scar(scholar, "defection", former_employer, timestamp)
            scholar.contract["employer"] = new_faction
            scholar.memory.adjust_feeling(former_employer, -4.0)
            outcome = "defected"
            press = defection_notice(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="defected",
                    new_faction=new_faction,
                    probability=probability,
                )
            )
            resolve_at = timestamp + self._FOLLOWUP_DELAYS["defection_return"]
            self.state.schedule_followup(
                scholar_id,
                "defection_return",
                resolve_at,
                {
                    "former_employer": former_employer,
                    "new_faction": new_faction,
                    "scenario": "reconciliation",
                },
            )
        else:
            scholar.memory.adjust_feeling(new_faction, -2.0)
            outcome = "refused"
            press = defection_notice(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="refused",
                    new_faction=new_faction,
                    probability=probability,
                )
            )
            resolve_at = timestamp + self._FOLLOWUP_DELAYS["defection_grudge"]
            self.state.schedule_followup(
                scholar_id,
                "defection_grudge",
                resolve_at,
                {
                    "faction": new_faction,
                    "probability": probability,
                    "former_employer": former_employer,
                    "scenario": "rivalry",
                },
            )
        base_body = press.body
        persona_traits = self._resolve_scholar_traits(scholar.name)
        press = self._enhance_press_release(
            press,
            base_body=base_body,
            persona_name=scholar.name,
            persona_traits=persona_traits,
            extra_context={
                "scholar": scholar.name,
                "outcome": outcome,
                "probability": probability,
                "new_faction": new_faction,
                "relationship_modifier": relationship_effect,
            },
        )
        press.metadata.update(
            {
                "probability": probability,
                "relationship_modifier": relationship_effect,
                "relationship_details": relationship,
                "former_employer": former_employer,
                "new_faction": new_faction,
                "offer_quality": offer_quality,
                "mistreatment": mistreatment,
                "alignment": alignment,
                "plateau": plateau,
            }
        )
        self.state.save_scholar(scholar)
        self._archive_press(press, timestamp)
        depth = self._multi_press.determine_depth(
            event_type="defection",
            is_first_time=outcome == "defected",
        )
        layers = self._multi_press.generate_defection_layers(
            DefectionContext(
                scholar=scholar.name,
                outcome=outcome,
                new_faction=new_faction,
                probability=probability,
            ),
            scholar,
            former_employer,
            list(self.state.all_scholars()),
            depth,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={press.type},
            timestamp=timestamp,
            event_type="defection",
        )
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="defection_evaluated",
                payload={
                    "scholar": scholar_id,
                    "probability": probability,
                    "roll": roll,
                    "outcome": outcome,
                    "new_faction": new_faction,
                },
            )
        )
        return outcome == "defected", press

    # ===== New Offer System Methods =====
    def create_defection_offer(
        self,
        rival_id: str,
        scholar_id: str,
        target_faction: str,
        influence_offer: Dict[str, int],
        terms: Optional[Dict[str, object]] = None,
    ) -> Tuple[int, List[PressRelease]]:
        """Create a new defection offer to poach a scholar.

        Returns:
            (offer_id, press_releases) tuple
        """
        self._ensure_not_paused()
        timestamp = datetime.now(timezone.utc)
        scholar = self.state.get_scholar(scholar_id)
        rival = self.state.get_player(rival_id)

        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")
        if not rival:
            raise ValueError(f"Player {rival_id} not found")

        # Find current patron
        patron_id = scholar.contract.get("employer", "")
        if not patron_id:
            raise ValueError(f"Scholar {scholar_id} has no current employer")

        # Validate rival has enough influence
        for faction, amount in influence_offer.items():
            if rival.influence.get(faction, 0) < amount:
                raise ValueError(f"Player {rival_id} has insufficient {faction} influence")

        # Create the offer record
        offer = OfferRecord(
            scholar_id=scholar_id,
            faction=target_faction,
            rival_id=rival_id,
            patron_id=patron_id,
            offer_type="initial",
            influence_offered=influence_offer,
            terms=terms or {},
            status="pending",
            created_at=timestamp,
        )

        offer_id = self.state.save_offer(offer)
        offer.id = offer_id

        # Schedule followup for offer evaluation (24 hour negotiation window)
        resolve_at = timestamp + timedelta(hours=24)
        self.state.schedule_followup(
            scholar_id,
            "evaluate_offer",
            resolve_at,
            {"offer_id": offer_id},
        )

        # Generate press releases
        press = []
        headline = f"Poaching Attempt: {rival.display_name} Targets {scholar.name}"
        body = f"{rival.display_name} has made an offer to {scholar.name} to join {target_faction}.\n"
        body += f"The offer includes: {', '.join(f'{v} {k}' for k, v in influence_offer.items())} influence.\n"
        if terms:
            body += f"Additional terms: {terms}\n"
        body += f"Current patron {patron_id} has 24 hours to counter."

        release = PressRelease(
            type="negotiation",
            headline=headline,
            body=body,
            metadata={
                "offer_id": offer_id,
                "rival": rival_id,
                "patron": patron_id,
                "scholar": scholar_id,
            }
        )
        self._archive_press(release, timestamp)
        press.append(release)

        # Deduct influence from rival (held in escrow)
        for faction, amount in influence_offer.items():
            rival.influence[faction] -= amount
        self.state.upsert_player(rival)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="offer_created",
                payload={
                    "offer_id": offer_id,
                    "rival": rival_id,
                    "scholar": scholar_id,
                    "influence": influence_offer,
                }
            )
        )

        return offer_id, press

    def counter_offer(
        self,
        player_id: str,
        original_offer_id: int,
        counter_influence: Dict[str, int],
        counter_terms: Optional[Dict[str, object]] = None,
    ) -> Tuple[int, List[PressRelease]]:
        """Create a counter-offer to retain a scholar.

        Returns:
            (counter_offer_id, press_releases) tuple
        """
        self._ensure_not_paused()
        timestamp = datetime.now(timezone.utc)
        original = self.state.get_offer(original_offer_id)
        player = self.state.get_player(player_id)

        if not original:
            raise ValueError(f"Offer {original_offer_id} not found")
        if not player:
            raise ValueError(f"Player {player_id} not found")

        # Verify this player is the current patron
        if player_id != original.patron_id:
            raise ValueError(f"Player {player_id} is not the current patron")

        # Verify offer is still pending
        if original.status != "pending":
            raise ValueError(f"Offer {original_offer_id} is not pending (status: {original.status})")

        # Validate patron has enough influence
        for faction, amount in counter_influence.items():
            if player.influence.get(faction, 0) < amount:
                raise ValueError(f"Player {player_id} has insufficient {faction} influence")

        # Create counter-offer
        counter = OfferRecord(
            scholar_id=original.scholar_id,
            faction=original.faction,  # Keep same target faction for consistency
            rival_id=original.rival_id,
            patron_id=player_id,
            offer_type="counter",
            influence_offered=counter_influence,
            terms=counter_terms or {},
            status="pending",
            parent_offer_id=original_offer_id,
            created_at=timestamp,
        )

        counter_id = self.state.save_offer(counter)
        counter.id = counter_id

        # Update original offer status
        self.state.update_offer_status(original_offer_id, "countered")

        # Reschedule followup for counter evaluation (12 hours for final round)
        self.state.clear_followup(
            original_offer_id,
            status="cancelled",
            result={"reason": "counter_offer_supersedes"},
        )
        resolve_at = timestamp + timedelta(hours=12)
        self.state.schedule_followup(
            original.scholar_id,
            "evaluate_counter",
            resolve_at,
            {"counter_offer_id": counter_id},
        )

        # Generate press
        scholar = self.state.get_scholar(original.scholar_id)
        press = []
        headline = f"Counter-Offer: {player.display_name} Fights for {scholar.name}"
        body = f"{player.display_name} has countered with: {', '.join(f'{v} {k}' for k, v in counter_influence.items())} influence.\n"
        if counter_terms:
            body += f"Additional terms: {counter_terms}\n"
        body += "The rival has 12 hours to make a final offer."

        release = PressRelease(
            type="negotiation",
            headline=headline,
            body=body,
            metadata={
                "counter_offer_id": counter_id,
                "original_offer_id": original_offer_id,
            }
        )
        self._archive_press(release, timestamp)
        press.append(release)

        # Deduct influence from patron (held in escrow)
        for faction, amount in counter_influence.items():
            player.influence[faction] -= amount
        self.state.upsert_player(player)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="counter_offer_created",
                payload={
                    "counter_offer_id": counter_id,
                    "original_offer_id": original_offer_id,
                    "patron": player_id,
                    "influence": counter_influence,
                }
            )
        )

        return counter_id, press

    def evaluate_scholar_offer(self, offer_id: int) -> float:
        """Calculate a scholar's likelihood to accept an offer based on feelings and terms.

        Returns probability between 0.0 and 1.0
        """
        offer = self.state.get_offer(offer_id)
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        scholar = self.state.get_scholar(offer.scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {offer.scholar_id} not found")

        # Base probability from offer quality (influence amount)
        total_influence = sum(offer.influence_offered.values())
        offer_quality = min(10.0, total_influence / 10.0)  # Scale to 0-10

        # Relationship adjustments from mentorship/sidecasts and feelings
        rival_relationship = self._relationship_bonus(scholar, offer.rival_id)
        patron_relationship = self._relationship_bonus(scholar, offer.patron_id)

        rival_feeling = scholar.memory.feelings.get(offer.rival_id, 0.0)
        patron_feeling = scholar.memory.feelings.get(offer.patron_id, 0.0)

        # Mistreatment factor (negative feelings toward current patron)
        mistreatment = max(0.0, -patron_feeling) / 5.0  # Scale negative feelings

        # Alignment factor (positive feelings toward rival)
        alignment = max(0.0, rival_feeling) / 5.0

        # Check for plateau (no recent discoveries)
        recent_discoveries = [
            fact for fact in scholar.memory.facts
            if fact.kind == "discovery" and
            (datetime.now(timezone.utc) - fact.when).days < 90
        ]
        plateau = 0.0 if recent_discoveries else 0.2

        # Use existing defection probability calculation
        from .scholars import defection_probability
        probability = defection_probability(scholar, offer_quality, mistreatment, alignment, plateau)

        # Apply relationship bonuses: rival increases, patron decreases
        probability += rival_relationship["total"]
        probability -= patron_relationship["total"]

        # Adjust for contract terms
        if "exclusive_research" in offer.terms:
            probability += 0.1
        if "guaranteed_funding" in offer.terms:
            probability += 0.15
        if "leadership_role" in offer.terms:
            probability += 0.2

        # Adjust for offer type (counters have slight advantage)
        if offer.offer_type == "counter":
            probability -= 0.1  # Loyalty bonus to current patron

        probability = self._clamp_probability(probability)

        return probability

    def resolve_offer_negotiation(
        self,
        offer_id: int,
    ) -> List[PressRelease]:
        """Resolve a negotiation chain and determine the final outcome.

        This is called by the scheduler when negotiations time out.
        """
        timestamp = datetime.now(timezone.utc)
        offer_chain = self.state.get_offer_chain(offer_id)

        if not offer_chain:
            raise ValueError(f"No offer chain found for {offer_id}")

        # Find the best offer in the chain
        best_offer = None
        best_probability = 0.0

        for offer in offer_chain:
            if offer.status == "pending":
                prob = self.evaluate_scholar_offer(offer.id)
                if prob > best_probability:
                    best_probability = prob
                    best_offer = offer

        if not best_offer:
            # No valid offers, scholar stays
            press = []
            for offer in offer_chain:
                self.state.update_offer_status(offer.id, "expired", timestamp)
                # Return escrowed influence
                player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                for faction, amount in offer.influence_offered.items():
                    player.influence[faction] += amount
                self.state.upsert_player(player)
            return press

        # Roll for acceptance
        roll = self._rng.uniform(0.0, 1.0)
        scholar = self.state.get_scholar(best_offer.scholar_id)
        press = []

        rival_relationship = self._relationship_bonus(scholar, best_offer.rival_id)
        patron_relationship = self._relationship_bonus(scholar, best_offer.patron_id)

        if roll < best_probability:
            # Scholar accepts the offer
            winner_id = best_offer.rival_id if best_offer.offer_type == "initial" else best_offer.patron_id
            loser_id = best_offer.patron_id if best_offer.offer_type == "initial" else best_offer.rival_id
            winner_player = self.state.get_player(winner_id)
            winner_name = winner_player.display_name if winner_player else winner_id

            # Transfer scholar
            old_employer = scholar.contract.get("employer", "")
            scholar.contract["employer"] = best_offer.faction if best_offer.offer_type == "initial" else old_employer

            # Apply emotional consequences
            from .scholars import apply_scar
            if best_offer.offer_type == "initial":
                # Defection - apply scar and negative feelings
                apply_scar(scholar, "defection", old_employer, timestamp)
                scholar.memory.adjust_feeling(old_employer, -4.0)
                scholar.memory.adjust_feeling(winner_id, 2.0)
            else:
                # Stayed with patron - positive feelings
                scholar.memory.adjust_feeling(winner_id, 3.0)
                scholar.memory.adjust_feeling(loser_id, -2.0)

            self.state.save_scholar(scholar)

            # Create press release
            headline = f"{scholar.name} {'Defects to' if best_offer.offer_type == 'initial' else 'Remains with'} {winner_id}"
            body = f"After intense negotiations, {scholar.name} has chosen to {'join' if best_offer.offer_type == 'initial' else 'remain with'} {winner_id}.\n"
            body += f"Winning offer: {', '.join(f'{v} {k}' for k, v in best_offer.influence_offered.items())} influence.\n"
            body += f"Probability of acceptance was {best_probability:.1%}."

            release = PressRelease(
                type="negotiation_resolved",
                headline=headline,
                body=body,
                metadata={
                    "scholar": scholar.id,
                    "winner": winner_id,
                    "loser": loser_id,
                    "offer_id": best_offer.id,
                    "probability": best_probability,
                    "relationship_rival": rival_relationship,
                    "relationship_patron": patron_relationship,
                }
            )
            release = self._enhance_press_release(
                release,
                base_body=body,
                persona_name=winner_name,
                persona_traits=None,
                extra_context={
                    "scholar": scholar.name,
                    "winner": winner_name,
                    "loser": loser_id,
                    "offer_id": best_offer.id,
                    "probability": best_probability,
                    "relationship_rival": rival_relationship["total"],
                    "relationship_patron": patron_relationship["total"],
                },
            )
            self._archive_press(release, timestamp)
            press.append(release)
            new_faction = best_offer.faction if best_offer.offer_type == "initial" else old_employer
            depth = self._multi_press.determine_depth(
                event_type="defection",
                is_first_time=best_offer.offer_type == "initial",
            )
            layers = self._multi_press.generate_defection_layers(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="defected" if best_offer.offer_type == "initial" else "remained",
                    new_faction=new_faction,
                    probability=best_probability,
                ),
                scholar,
                old_employer or "Independent",
                list(self.state.all_scholars()),
                depth,
            )
            extra_layers = self._apply_multi_press_layers(
                layers,
                skip_types={release.type},
                timestamp=timestamp,
                event_type="defection",
            )
            press.extend(extra_layers)

            # Mark all offers as resolved
            for offer in offer_chain:
                status = "accepted" if offer.id == best_offer.id else "rejected"
                self.state.update_offer_status(offer.id, status, timestamp)

            # Return escrowed influence for losing offers
            for offer in offer_chain:
                if offer.id != best_offer.id:
                    player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                    for faction, amount in offer.influence_offered.items():
                        player.influence[faction] += amount
                    self.state.upsert_player(player)

            # Winner pays the influence cost (already deducted)
            # No need to return it

            # Schedule followup for potential return (if defected)
            if best_offer.offer_type == "initial":
                resolve_at = timestamp + self._FOLLOWUP_DELAYS.get("defection_return", timedelta(days=30))
                self.state.schedule_followup(
                    scholar.id,
                    "defection_return",
                    resolve_at,
                    {"former_employer": old_employer, "new_faction": best_offer.faction},
                )

        else:
            # Scholar rejects all offers
            headline = f"{scholar.name} Rejects All Offers"
            body = f"{scholar.name} has decided to remain with their current patron.\n"
            body += f"Best offer had {best_probability:.1%} chance of success but failed."

            release = PressRelease(
                type="negotiation_resolved",
                headline=headline,
                body=body,
                metadata={
                    "scholar": scholar.id,
                    "all_rejected": True,
                    "probability": best_probability,
                    "relationship_rival": rival_relationship,
                    "relationship_patron": patron_relationship,
                }
            )
            release = self._enhance_press_release(
                release,
                base_body=body,
                persona_name=scholar.name,
                persona_traits=self._resolve_scholar_traits(scholar.name),
                extra_context={
                    "scholar": scholar.name,
                    "offer_chain": [o.id for o in offer_chain],
                    "outcome": "rejected",
                    "probability": best_probability,
                    "relationship_rival": rival_relationship["total"],
                    "relationship_patron": patron_relationship["total"],
                },
            )
            self._archive_press(release, timestamp)
            press.append(release)
            depth = self._multi_press.determine_depth(event_type="defection")
            layers = self._multi_press.generate_defection_layers(
                DefectionContext(
                    scholar=scholar.name,
                    outcome="refused",
                    new_faction=scholar.contract.get("employer", ""),
                    probability=best_probability,
                ),
                scholar,
                scholar.contract.get("employer", ""),
                list(self.state.all_scholars()),
                depth,
            )
            extra_layers = self._apply_multi_press_layers(
                layers,
                skip_types={release.type},
                timestamp=timestamp,
                event_type="defection",
            )
            press.extend(extra_layers)

            # Mark all offers as rejected and return influence
            for offer in offer_chain:
                self.state.update_offer_status(offer.id, "rejected", timestamp)
                player = self.state.get_player(offer.rival_id if offer.offer_type == "initial" else offer.patron_id)
                for faction, amount in offer.influence_offered.items():
                    player.influence[faction] += amount
                self.state.upsert_player(player)

            # Adjust feelings
            scholar.memory.adjust_feeling(best_offer.rival_id, -1.0)
            self.state.save_scholar(scholar)

        # Record event
        self.state.append_event(
            Event(
                timestamp=timestamp,
                action="negotiation_resolved",
                payload={
                    "offer_chain": [o.id for o in offer_chain],
                    "best_offer": best_offer.id if best_offer else None,
                    "probability": best_probability,
                    "roll": roll,
                    "accepted": roll < best_probability,
                    "relationship_rival": rival_relationship if best_offer else None,
                    "relationship_patron": patron_relationship if best_offer else None,
                }
            )
        )

        return press

    def list_player_offers(self, player_id: str) -> List[OfferRecord]:
        """Get all active offers involving a player."""
        return self.state.list_active_offers(player_id)

    def player_status(self, player_id: str) -> Optional[Dict[str, object]]:
        player = self.state.get_player(player_id)
        if not player:
            return None
        self._ensure_influence_structure(player)
        cap = self._influence_cap(player)
        thresholds = {
            action: value for action, value in self.settings.action_thresholds.items()
        }
        contracts = self._contract_summary_for_player(player)
        relationships = self._player_relationship_summary(player)
        commitments = self._player_commitment_summary(player)
        investments = self._player_investment_summary(player)
        endowments = self._player_endowment_summary(player)
        return {
            "id": player.id,
            "display_name": player.display_name,
            "player": player.display_name,  # Keep for backward compatibility
            "reputation": player.reputation,
            "influence": dict(player.influence),
            "influence_cap": cap,
            "cooldowns": dict(player.cooldowns),
            "thresholds": thresholds,
            "contracts": contracts,
            "relationships": relationships,
            "commitments": commitments,
            "investments": investments,
            "endowments": endowments,
        }

    def roster_status(self) -> List[Dict[str, object]]:
        """Get status information for all scholars in the roster."""
        roster = []
        for scholar in self.state.all_scholars():
            roster.append({
                "id": scholar.id,
                "name": scholar.name,
                "archetype": scholar.archetype,
                "stats": scholar.stats,
                "memory": {
                    "facts": scholar.memory.facts,
                    "feelings": scholar.memory.feelings,
                    "scars": scholar.memory.scars,
                }
            })
        return roster

    def archive_digest(self) -> PressRelease:
        """Generate a summary digest of recent game events."""
        # Get recent press releases
        recent_press = self.state.list_press_releases(limit=10)

        # Count events by type
        event_counts = {}
        for press_record in recent_press:
            event_type = press_record.release.type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        # Generate summary body
        body_lines = ["Summary of recent events:"]

        if event_counts:
            for event_type, count in sorted(event_counts.items()):
                body_lines.append(f"- {count} {event_type.replace('_', ' ').title()} events")
        else:
            body_lines.append("- No recent events to report")

        # Add some recent headlines
        if recent_press:
            body_lines.append("\nRecent headlines:")
            for press_record in recent_press[:3]:
                body_lines.append(f"- {press_record.release.headline}")

        release = PressRelease(
            type="archive_digest",
            headline="Archive Digest",
            body="\n".join(body_lines),
            metadata={"event_count": len(recent_press)}
        )

        # Archive the digest itself
        self._archive_press(release, datetime.now(timezone.utc))

        return release

    def queue_mentorship(
        self,
        player_id: str,
        scholar_id: str,
        career_track: str | None = None,
    ) -> PressRelease:
        """Queue a mentorship for the next digest resolution."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        # Check if scholar already has an active mentorship
        existing = self.state.get_active_mentorship(scholar_id)
        if existing:
            raise ValueError(f"Scholar {scholar_id} already has an active mentor")

        # Queue the mentorship
        mentorship_id = self.state.add_mentorship(player_id, scholar_id, career_track)
        self.state.enqueue_order(
            "mentorship_activation",
            actor_id=player_id,
            subject_id=scholar_id,
            payload={
                "mentorship_id": mentorship_id,
                "scholar_id": scholar_id,
                "career_track": career_track,
            },
            source_table="mentorships",
            source_id=str(mentorship_id),
        )

        # Generate press release
        quote = f"I shall guide {scholar.name} towards greater achievements."
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Mentorship of {scholar.name}",
            )
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=player.display_name,
            persona_traits=None,
            extra_context={
                "event": "mentorship_queued",
                "player": player.display_name,
                "scholar": scholar.name,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="mentorship_queued",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "career_track": career_track,
                    "mentorship_id": mentorship_id,
                },
            )
        )

        layers = self._multi_press.generate_mentorship_layers(
            mentor=player.display_name,
            scholar=scholar,
            phase="queued",
            track=career_track,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={press.type},
            timestamp=now,
            event_type="mentorship",
        )

        return press

    def assign_lab(
        self,
        player_id: str,
        scholar_id: str,
        career_track: str,
    ) -> PressRelease:
        """Assign a scholar to a new career track (Academia or Industry)."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        if career_track not in self._CAREER_TRACKS:
            raise ValueError(f"Invalid career track: {career_track}. Choose from {list(self._CAREER_TRACKS.keys())}")

        # Check if player is mentoring this scholar
        mentorship = self.state.get_active_mentorship(scholar_id)
        if not mentorship or mentorship[1] != player_id:
            raise ValueError(f"You must be actively mentoring {scholar.name} to assign their lab")

        # Update scholar's career track
        old_track = scholar.career.get("track", "Academia")
        scholar.career["track"] = career_track

        # Reset to first tier of new track if changing tracks
        if old_track != career_track:
            scholar.career["tier"] = self._CAREER_TRACKS[career_track][0]
            scholar.career["ticks"] = 0

        self.state.save_scholar(scholar)

        # Generate press release
        quote = f"{scholar.name} has been assigned to the {career_track} track under my mentorship."
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Lab assignment for {scholar.name}",
            )
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=player.display_name,
            persona_traits=None,
            extra_context={
                "event": "assign_lab",
                "player": player.display_name,
                "scholar": scholar.name,
                "career_track": career_track,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="lab_assigned",
                payload={
                    "player": player_id,
                    "scholar": scholar_id,
                    "career_track": career_track,
                    "old_track": old_track,
                },
            )
        )

        return press

    def launch_conference(
        self,
        player_id: str,
        theory_id: int,
        confidence: ConfidenceLevel,
        supporters: List[str],
        opposition: List[str],
    ) -> PressRelease:
        """Queue a conference to debate a theory with public reputation stakes."""
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        # Check if theory exists
        theory_data = self.state.get_theory_by_id(theory_id)
        if not theory_data:
            raise ValueError(f"Theory {theory_id} not found")
        _, theory = theory_data

        # Generate unique conference code
        code = f"CONF-{self._rng.randint(1000, 9999)}"

        # Validate supporters and opposition are scholars
        all_scholars = {s.id for s in self.state.all_scholars()}
        for scholar_id in supporters:
            if scholar_id not in all_scholars:
                raise ValueError(f"Scholar {scholar_id} not found")
        for scholar_id in opposition:
            if scholar_id not in all_scholars:
                raise ValueError(f"Scholar {scholar_id} not found")

        # Queue the conference
        self.state.add_conference(
            code=code,
            player_id=player_id,
            theory_id=theory_id,
            confidence=confidence.value,
            supporters=supporters,
            opposition=opposition,
        )
        self.state.enqueue_order(
            "conference_resolution",
            actor_id=player_id,
            subject_id=code,
            payload={
                "conference_code": code,
                "theory_id": theory_id,
                "confidence": confidence.value,
                "supporters": supporters,
                "opposition": opposition,
            },
            source_table="conferences",
            source_id=code,
        )

        # Generate press release
        supporter_names = [s.name for s in self.state.all_scholars() if s.id in supporters]
        opposition_names = [s.name for s in self.state.all_scholars() if s.id in opposition]

        quote = f"Conference {code} announced to debate: {theory.theory}"
        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=quote,
                trigger=f"Conference on theory #{theory_id}",
            )
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="conference_launched",
                payload={
                    "code": code,
                    "player": player_id,
                    "theory_id": theory_id,
                    "confidence": confidence.value,
                    "supporters": supporters,
                    "opposition": opposition,
                },
            )
        )

        return press

    def resolve_conferences(self) -> List[PressRelease]:
        """Resolve all pending conferences during digest."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)

        due_orders = self.state.fetch_due_orders("conference_resolution", now)
        for order in due_orders:
            order_id = order["id"]
            payload = order["payload"]
            code = payload.get("conference_code") or order.get("subject_id")
            if not code:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "missing_code"},
                )
                continue

            conference = self.state.get_conference_by_code(code)
            if not conference:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "conference_missing"},
                )
                continue

            code, player_id, theory_id, confidence_str, supporters, opposition, _ = conference
            player = self.state.get_player(player_id)
            theory_data = self.state.get_theory_by_id(theory_id)
            if not player or not theory_data:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "conference_context_missing"},
                )
                continue
            _, theory = theory_data

            confidence = ConfidenceLevel(confidence_str)

            base_roll = self._rng.randint(1, 100)
            support_modifier = len(supporters) * 5
            opposition_modifier = len(opposition) * 5
            final_roll = base_roll + support_modifier - opposition_modifier

            if final_roll >= 60:
                outcome = ExpeditionOutcome.SUCCESS
            elif final_roll >= 40:
                outcome = ExpeditionOutcome.PARTIAL
            else:
                outcome = ExpeditionOutcome.FAILURE

            reputation_delta = self._confidence_delta(confidence, outcome)
            player.adjust_reputation(
                reputation_delta,
                self.settings.reputation_bounds["min"],
                self.settings.reputation_bounds["max"],
            )
            self.state.upsert_player(player)

            self.state.resolve_conference(
                code=code,
                outcome=outcome.value,
                reputation_delta=reputation_delta,
                result_payload={
                    "roll": base_roll,
                    "support_modifier": support_modifier,
                    "opposition_modifier": opposition_modifier,
                    "final_roll": final_roll,
                },
            )

            outcome_text = {
                ExpeditionOutcome.SUCCESS: "The conference concluded with resounding support for the theory",
                ExpeditionOutcome.PARTIAL: "The conference ended with mixed opinions",
                ExpeditionOutcome.FAILURE: "The conference thoroughly rejected the theory",
            }[outcome]

            quote = f"Conference {code} result: {outcome_text}. Reputation change: {reputation_delta:+d}"
            press = academic_gossip(
                GossipContext(
                    scholar="The Academy",
                    quote=quote,
                    trigger=f"Conference {code} resolution",
                )
            )

            releases.append(press)
            self._archive_press(press, now)

            self.state.append_event(
                Event(
                    timestamp=now,
                    action="conference_resolved",
                    payload={
                        "code": code,
                        "outcome": outcome.value,
                        "reputation_delta": reputation_delta,
                        "final_roll": final_roll,
                    },
                )
            )
            self.state.update_order_status(
                order_id,
                "completed",
                result={"outcome": outcome.value},
            )

        return releases

    def submit_symposium_proposal(
        self,
        player_id: str,
        topic: str,
        description: str,
    ) -> PressRelease:
        """Allow players to submit symposium topic proposals."""

        self._ensure_not_paused()
        if not topic.strip():
            raise ValueError("Topic cannot be empty")
        if not description.strip():
            raise ValueError("Description cannot be empty")

        self.ensure_player(player_id)
        now = datetime.now(timezone.utc)
        expired_ids = self.state.expire_symposium_proposals(now)
        if expired_ids:
            self._queue_admin_notification(
                f"🗂️ Expired {len(expired_ids)} symposium proposal(s) during new submission."
            )

        pending_count = self.state.count_pending_symposium_proposals(now=now)
        if pending_count >= self.settings.symposium_max_backlog:
            raise ValueError("Proposal backlog is full; wait for pending topics to be scheduled.")

        player_pending = self.state.count_player_pending_symposium_proposals(
            player_id, now=now
        )
        if player_pending >= self.settings.symposium_max_per_player:
            raise ValueError(
                "You already have the maximum number of active proposals. Wait for one to resolve."
            )

        expire_at = now + timedelta(days=self.settings.symposium_proposal_expiry_days)
        priority = int(now.timestamp())
        proposal_id = self.state.submit_symposium_proposal(
            player_id=player_id,
            topic=topic.strip(),
            description=description.strip(),
            created_at=now,
            expire_at=expire_at,
            priority=priority,
        )

        player = self.state.get_player(player_id)
        display_name = player.display_name if player else player_id
        press = PressRelease(
            type="symposium_proposal",
            headline=f"Symposium Proposal Submitted — {topic.strip()}",
            body=(
                f"{display_name} proposes this week's symposium: {topic.strip()}\n\n"
                f"{description.strip()}\n\n"
                "Peers may review proposals with /symposium_proposals.\n"
                f"This proposal expires on {expire_at.strftime('%Y-%m-%d')} if not selected."
            ),
            metadata={
                "proposal_id": proposal_id,
                "player_id": player_id,
                "topic": topic.strip(),
                "expires_at": expire_at.isoformat(),
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=display_name,
            persona_traits=None,
            extra_context={
                "event": "symposium_proposal",
                "topic": topic.strip(),
            },
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_proposal_submitted",
                payload={
                    "proposal_id": proposal_id,
                    "player": player_id,
                    "topic": topic.strip(),
                    "expires_at": expire_at.isoformat(),
                },
            )
        )

        return press

    def list_symposium_proposals(self, *, limit: int = 5) -> List[Dict[str, object]]:
        """Return pending symposium proposals with proposer display names."""

        now = datetime.now(timezone.utc)
        proposals = self.state.list_pending_symposium_proposals(limit=limit, now=now)
        enriched: List[Dict[str, object]] = []
        for proposal in proposals:
            player = self.state.get_player(proposal["player_id"])
            enriched.append(
                {
                    "id": proposal["id"],
                    "topic": proposal["topic"],
                    "description": proposal["description"],
                    "created_at": proposal["created_at"],
                    "player_id": proposal["player_id"],
                    "expires_at": proposal.get("expire_at"),
                    "priority": proposal.get("priority", 0),
                    "proposer": player.display_name if player else proposal["player_id"],
                }
            )
        return enriched

    def symposium_pledge_status(self, player_id: str) -> Dict[str, object]:
        """Return pledge/grace state for the requested player."""

        self.ensure_player(player_id)
        player = self.state.get_player(player_id)
        assert player is not None

        participation = self.state.get_symposium_participation(player_id)
        grace_limit = self.settings.symposium_grace_misses
        miss_streak = int(participation.get("miss_streak", 0)) if participation else 0
        grace_used = int(participation.get("grace_miss_consumed", 0)) if participation else 0
        grace_remaining = max(0, grace_limit - grace_used)
        grace_window_start = (
            participation.get("grace_window_start") if participation else None
        )
        last_voted_at = participation.get("last_voted_at") if participation else None
        raw_debts = self.state.list_symposium_debts(player_id)
        cooldown_days = self.settings.symposium_debt_reprisal_cooldown_days
        cooldown_delta = timedelta(days=cooldown_days)
        debts_payload = []
        for entry in raw_debts:
            last_reprisal_at = entry.get("last_reprisal_at")
            next_reprisal_at = None
            if isinstance(last_reprisal_at, datetime):
                next_reprisal_at = last_reprisal_at + cooldown_delta
            debts_payload.append(
                {
                    "faction": entry.get("faction"),
                    "amount": entry.get("amount", 0),
                    "reprisal_level": entry.get("reprisal_level", 0),
                    "created_at": entry.get("created_at").isoformat()
                    if isinstance(entry.get("created_at"), datetime)
                    else None,
                    "updated_at": entry.get("updated_at").isoformat()
                    if isinstance(entry.get("updated_at"), datetime)
                    else None,
                    "last_reprisal_at": last_reprisal_at.isoformat()
                    if isinstance(last_reprisal_at, datetime)
                    else None,
                    "next_reprisal_at": next_reprisal_at.isoformat()
                    if isinstance(next_reprisal_at, datetime)
                    else None,
                    "cooldown_days": cooldown_days,
                }
            )

        current_topic = self.state.get_current_symposium_topic()
        current_summary: Optional[Dict[str, object]] = None
        if current_topic is not None:
            topic_id, topic, description, proposal_id, _ = current_topic
            pledge = self.state.get_symposium_pledge(topic_id=topic_id, player_id=player_id)
            if pledge:
                current_summary = {
                    "topic_id": topic_id,
                    "topic": topic,
                    "pledge_amount": pledge["pledge_amount"],
                    "faction": pledge.get("faction"),
                    "status": pledge.get("status"),
                    "created_at": (
                        pledge["created_at"].isoformat() if pledge.get("created_at") else None
                    ),
                    "resolved_at": (
                        pledge["resolved_at"].isoformat() if pledge.get("resolved_at") else None
                    ),
                }
            else:
                current_summary = {
                    "topic_id": topic_id,
                    "topic": topic,
                    "pledge_amount": self.settings.symposium_pledge_base + miss_streak,
                    "faction": self._select_pledge_faction(player),
                    "status": "none",
                }

        history = self.state.list_recent_symposium_pledges_for_player(player_id, limit=5)
        history_payload = [
            {
                "topic_id": entry["topic_id"],
                "topic": entry["topic"],
                "symposium_date": entry["symposium_date"].isoformat()
                if entry.get("symposium_date")
                else None,
                "pledge_amount": entry["pledge_amount"],
                "faction": entry["faction"],
                "status": entry["status"],
                "created_at": entry["created_at"].isoformat()
                if entry.get("created_at")
                else None,
                "resolved_at": entry["resolved_at"].isoformat()
                if entry.get("resolved_at")
                else None,
            }
            for entry in history
        ]

        return {
            "player_id": player.id,
            "display_name": player.display_name,
            "miss_streak": miss_streak,
            "grace_remaining": grace_remaining,
            "grace_limit": grace_limit,
            "grace_window_start": grace_window_start.isoformat()
            if isinstance(grace_window_start, datetime)
            else None,
            "last_voted_at": last_voted_at.isoformat()
            if isinstance(last_voted_at, datetime)
            else None,
            "current": current_summary,
            "history": history_payload,
            "debts": debts_payload,
            "outstanding_debt": sum(debt["amount"] for debt in raw_debts),
        }

    def symposium_backlog_report(self) -> Dict[str, object]:
        """Return the current backlog scoring snapshot for Discord surfaces."""

        now = datetime.now(timezone.utc)
        proposals = self.state.list_pending_symposium_proposals(now=now)
        backlog_cap = self.settings.symposium_max_backlog
        score_snapshot = []
        for entry in self._latest_symposium_scoring:
            created_at = entry.get("created_at")
            score_snapshot.append(
                {
                    "proposal_id": entry.get("proposal_id"),
                    "topic": entry.get("topic"),
                    "player_id": entry.get("player_id"),
                    "score": entry.get("score"),
                    "age_days": entry.get("age_days"),
                    "age_contribution": entry.get("age_contribution"),
                    "fresh_bonus": entry.get("fresh_bonus"),
                    "repeat_penalty": entry.get("repeat_penalty"),
                    "recent_proposer": entry.get("recent_proposer", False),
                    "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
                }
            )
        player_names: Dict[str, str] = {}
        for proposal in proposals:
            player = self.state.get_player(proposal["player_id"])
            if player:
                player_names[proposal["player_id"]] = player.display_name
        def _display_name(player_id: str) -> str:
            if player_id in player_names:
                return player_names[player_id]
            player = self.state.get_player(player_id)
            if player:
                player_names[player_id] = player.display_name
                return player.display_name
            return player_id
        for entry in score_snapshot:
            entry["display_name"] = _display_name(entry["player_id"])
        slots_remaining = max(0, backlog_cap - len(proposals))
        debt_summary: Dict[str, int] = {}
        debt_rows: List[Dict[str, object]] = []
        cooldown_days = self.settings.symposium_debt_reprisal_cooldown_days
        cooldown_delta = timedelta(days=cooldown_days)
        total_outstanding = 0
        for player in self.state.all_players():
            debts = self.state.list_symposium_debts(player.id)
            if not debts:
                continue
            for debt in debts:
                amount = debt.get("amount", 0)
                faction = debt.get("faction")
                created_at = debt.get("created_at")
                updated_at = debt.get("updated_at")
                last_reprisal_at = debt.get("last_reprisal_at")
                next_reprisal_at = None
                if isinstance(last_reprisal_at, datetime):
                    next_reprisal_at = last_reprisal_at + cooldown_delta
                debt_rows.append(
                    {
                        "player_id": player.id,
                        "display_name": player.display_name,
                        "faction": faction,
                        "amount": amount,
                        "reprisal_level": debt.get("reprisal_level", 0),
                        "last_reprisal_at": last_reprisal_at.isoformat()
                        if isinstance(last_reprisal_at, datetime)
                        else None,
                        "next_reprisal_at": next_reprisal_at.isoformat()
                        if isinstance(next_reprisal_at, datetime)
                        else None,
                        "cooldown_days": cooldown_days,
                        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
                        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
                    }
                )
                debt_summary[player.display_name] = (
                    debt_summary.get(player.display_name, 0) + amount
                )
                total_outstanding += amount
        return {
            "backlog_size": len(proposals),
            "slots_remaining": slots_remaining,
            "scoring": score_snapshot,
            "debts": debt_rows,
            "debt_summary": debt_summary,
            "debt_totals": {
                "total_outstanding": total_outstanding,
                "players_in_debt": len(debt_summary),
            },
            "config": {
                "max_backlog": backlog_cap,
                "recent_window": self.settings.symposium_recent_window,
                "fresh_bonus": self.settings.symposium_scoring_fresh_bonus,
                "repeat_penalty": self.settings.symposium_scoring_repeat_penalty,
                "age_weight": self.settings.symposium_scoring_age_weight,
                "max_age_days": self.settings.symposium_scoring_max_age_days,
            },
        }

    def start_symposium(
        self,
        topic: Optional[str] = None,
        description: Optional[str] = None,
        *,
        proposal_id: Optional[int] = None,
    ) -> PressRelease:
        """Start a new symposium, preferring player proposals when available."""

        self._ensure_not_paused()
        now = datetime.now(timezone.utc)
        expired_ids = self.state.expire_symposium_proposals(now)
        if expired_ids:
            self._queue_admin_notification(
                f"🗂️ Expired {len(expired_ids)} symposium proposal(s) prior to launch."
            )

        # Resolve any previous symposium first
        current = self.state.get_current_symposium_topic()
        if current:
            self.resolve_symposium()

        selected_proposal: Optional[Dict[str, object]] = None
        if topic is None or description is None:
            if proposal_id is not None:
                selected_proposal = self.state.get_symposium_proposal(proposal_id)
            if selected_proposal is None:
                selected_proposal = self._select_symposium_proposal(now)
            if selected_proposal:
                expires_at = selected_proposal.get("expire_at")
                if expires_at is not None and expires_at <= now:
                    # Proposal expired in the same tick; skip it.
                    self.state.update_symposium_proposal_status(
                        selected_proposal["id"],
                        status="expired",
                        selected_topic_id=None,
                    )
                    selected_proposal = None
                else:
                    topic = selected_proposal["topic"]
                    description = selected_proposal["description"]
                    proposal_id = selected_proposal["id"]
        if topic is None or description is None:
            topic, description = random.choice(_DEFAULT_SYMPOSIUM_TOPICS)
            proposal_id = None
            selected_proposal = None

        topic = topic.strip()
        description = description.strip()

        topic_id = self.state.create_symposium_topic(
            symposium_date=now,
            topic=topic,
            description=description,
            proposal_id=proposal_id,
        )
        if proposal_id is not None:
            self.state.update_symposium_proposal_status(
                proposal_id,
                status="selected",
                selected_topic_id=topic_id,
            )

        proposer_display = None
        if selected_proposal is not None:
            proposer = self.state.get_player(selected_proposal["player_id"])
            proposer_display = proposer.display_name if proposer else selected_proposal["player_id"]

        pledges = self._initialize_symposium_pledges(topic_id=topic_id, now=now)
        pledge_base = self.settings.symposium_pledge_base
        pledge_cap = self.settings.symposium_pledge_escalation_cap
        grace_misses = self.settings.symposium_grace_misses
        grace_window_days = self.settings.symposium_grace_window_days

        body_lines = [
            f"The Academy announces this week's symposium topic: {topic}",
            "",
            description,
            "",
            "Cast your votes with /symposium_vote:",
            "Option 1: Support the proposition",
            "Option 2: Oppose the proposition",
            "Option 3: Call for further study",
            "",
            (
                f"Silent scholars risk forfeiting {pledge_base} influence plus 1 per consecutive miss "
                f"(up to {pledge_base + pledge_cap})."
            ),
            (
                f"Everyone receives {grace_misses} grace miss per {grace_window_days}-day window; "
                "voting refreshes your grace."
            ),
        ]
        if proposer_display:
            body_lines.insert(1, f"Proposed by {proposer_display}.")
        pending_count = self.state.count_pending_symposium_proposals(now=now)
        total_pledged = sum(data["amount"] for data in pledges.values())
        slots_remaining = max(0, self.settings.symposium_max_backlog - pending_count)
        try:
            self._telemetry.track_game_progression(
                "symposium_pledges_created",
                float(total_pledged),
                details={
                    "topic_id": topic_id,
                    "players": len(pledges),
                },
            )
            self._telemetry.track_game_progression(
                "symposium_backlog_size",
                float(pending_count),
                details={
                    "slots_remaining": slots_remaining,
                },
            )
        except Exception:  # pragma: no cover - telemetry is optional
            logger.debug("Failed to record symposium telemetry", exc_info=True)
        body_lines.append("")
        body_lines.append(f"Backlog awaiting selection: {pending_count} proposal(s).")
        reprisal_notes = []
        for pledge_info in pledges.values():
            for reprisal in pledge_info.get("reprisals", []):
                faction = reprisal.get("faction")
                penalty_influence = reprisal.get("penalty_influence", 0)
                penalty_rep = reprisal.get("penalty_reputation", 0)
                if penalty_influence:
                    reprisal_notes.append(
                        f"{reprisal['display_name']} loses {penalty_influence} {faction} influence for sustained debt."
                    )
                elif penalty_rep:
                    reprisal_notes.append(
                        f"{reprisal['display_name']} suffers a reputation reprimand for unpaid symposium debt."
                    )
        if reprisal_notes:
            body_lines.append("")
            body_lines.append("Faction reprisals enacted:")
            body_lines.extend(f" - {note}" for note in reprisal_notes)
        press = PressRelease(
            type="symposium_announcement",
            headline=f"Symposium Topic: {topic}",
            body="\n".join(body_lines),
            metadata={
                "topic_id": topic_id,
                "topic": topic,
                "proposal_id": proposal_id,
                "pledge": {
                    "base": pledge_base,
                    "escalation_cap": pledge_cap,
                    "grace_misses": grace_misses,
                    "grace_window_days": grace_window_days,
                    "players": len(pledges),
                },
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name="The Academy",
            persona_traits=None,
            extra_context={
                "event": "symposium_started",
                "topic": topic,
            },
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_started",
                payload={
                    "topic_id": topic_id,
                    "topic": topic,
                    "proposal_id": proposal_id,
                    "pledges": pledges,
                },
            )
        )

        layers = self._multi_press.generate_symposium_layers(
            topic,
            description,
            phase="launch",
            scholars=list(self.state.all_scholars()),
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={press.type},
            timestamp=now,
            event_type="symposium",
        )

        self._schedule_symposium_reminders(
            topic_id=topic_id,
            topic=topic,
            start_time=now,
            pledge_base=pledge_base,
        )

        return press

    def vote_symposium(self, player_id: str, vote_option: int) -> PressRelease:
        """Record a player's vote on the current symposium topic."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError("Unknown player")

        current = self.state.get_current_symposium_topic()
        if not current:
            raise ValueError("No symposium is currently active")

        topic_id, topic, description, proposal_id, options = current

        if vote_option not in options:
            raise ValueError(f"Invalid vote option. Choose from {options}")

        # Record the vote
        self.state.record_symposium_vote(topic_id, player_id, vote_option)
        self.state.complete_symposium_reminders_for_player(topic_id, player_id)
        now = datetime.now(timezone.utc)
        self._record_symposium_vote_participation(player_id=player_id, voted_at=now)
        if self.state.get_symposium_pledge(topic_id=topic_id, player_id=player_id):
            self.state.update_symposium_pledge_status(
                topic_id=topic_id,
                player_id=player_id,
                status="fulfilled",
                resolved_at=now,
            )

        # Generate press release
        vote_text = {
            1: "supports the proposition",
            2: "opposes the proposition",
            3: "calls for further study",
        }[vote_option]

        press = academic_gossip(
            GossipContext(
                scholar=player.display_name,
                quote=f"I {vote_text} regarding {topic}.",
                trigger="Symposium vote",
            )
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=player.display_name,
            persona_traits=None,
            extra_context={
                "event": "symposium_vote",
                "topic": topic,
                "vote_option": vote_option,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_vote",
                payload={
                    "player": player_id,
                    "topic_id": topic_id,
                    "vote_option": vote_option,
                    "proposal_id": proposal_id,
                    "pledge_status": "fulfilled",
                },
            )
        )

        return press

    def symposium_call(self) -> List[PressRelease]:
        """Generate press releases for a symposium call."""
        self._ensure_not_paused()
        releases = []

        # Generate a symposium announcement
        release = PressRelease(
            type="symposium_announcement",
            headline="Weekly Symposium Call",
            body="The weekly symposium is now open for discussion. All scholars are invited to participate.",
        )
        release = self._enhance_press_release(
            release,
            base_body=release.body,
            persona_name="The Academy",
            persona_traits=None,
            extra_context={"event": "symposium_call"},
        )
        releases.append(release)

        # Add to press archive
        self.state.record_press_release(PressRecord(
            timestamp=datetime.now(timezone.utc),
            release=release,
        ))

        return releases

    def resolve_symposium(self) -> PressRelease:
        """Resolve the current symposium and announce the results."""
        self._ensure_not_paused()
        current = self.state.get_current_symposium_topic()
        if not current:
            return PressRelease(
                type="symposium_notice",
                headline="No Active Symposium",
                body="There is no symposium currently requiring resolution.",
                metadata={},
            )

        topic_id, topic, description, proposal_id, _ = current
        votes = self.state.get_symposium_votes(topic_id)

        # Determine winner
        if not votes:
            winner_text = "No consensus (no votes received)"
            winner = "none"
        else:
            winner_option = max(votes.keys(), key=lambda x: votes.get(x, 0))
            winner_count = votes[winner_option]
            total_votes = sum(votes.values())
            winner_text = {
                1: f"The proposition is supported ({winner_count}/{total_votes} votes)",
                2: f"The proposition is opposed ({winner_count}/{total_votes} votes)",
                3: f"Further study is required ({winner_count}/{total_votes} votes)",
            }[winner_option]
            winner = str(winner_option)

        # Resolve the topic
        self.state.resolve_symposium_topic(topic_id, winner)
        self.state.cancel_symposium_reminders(topic_id)

        topic_meta = self.state.get_symposium_topic(topic_id)
        if proposal_id and topic_meta is not None:
            self.state.update_symposium_proposal_status(
                proposal_id,
                status="resolved",
                selected_topic_id=topic_id,
            )
        # Generate press release with pledge outcomes
        player_records = list(self.state.all_players())
        voted_players = set(self.state.list_symposium_voters(topic_id))
        non_voter_players = [
            player for player in player_records if player.id not in voted_players
        ]
        penalty_records: List[Dict[str, object]] = []
        now = datetime.now(timezone.utc)
        for player in non_voter_players:
            pledge = self.state.get_symposium_pledge(topic_id=topic_id, player_id=player.id)
            if not pledge or pledge.get("status") in {"forfeited", "waived"}:
                continue
            penalty_record = self._handle_symposium_non_voter(
                topic_id=topic_id,
                player=player,
                pledge=pledge,
                now=now,
            )
            if penalty_record:
                penalty_records.append(penalty_record)
        # Ensure any pending pledges for voters are fulfilled
        for player in player_records:
            if player.id in voted_players:
                pledge = self.state.get_symposium_pledge(topic_id=topic_id, player_id=player.id)
                if pledge and pledge.get("status") == "pending":
                    self.state.update_symposium_pledge_status(
                        topic_id=topic_id,
                        player_id=player.id,
                        status="fulfilled",
                        resolved_at=now,
                    )

        non_voters = [player.display_name for player in non_voter_players]
        body_lines = [
            f"The symposium on '{topic}' has concluded.",
            "",
            f"Result: {winner_text}",
            "",
            "The Academy thanks all participants for their thoughtful contributions.",
        ]
        if non_voters:
            body_lines.append("")
            body_lines.append("Outstanding responses required from: " + ", ".join(non_voters))
        if penalty_records:
            body_lines.append("")
            body_lines.append("Participation stakes:")
            for record in penalty_records:
                if record["status"] == "waived":
                    body_lines.append(
                        f"- {record['display_name']} invoked grace; no influence forfeited."
                    )
                elif record["deducted"] > 0 and record["faction"]:
                    body_lines.append(
                        f"- {record['display_name']} forfeits {record['deducted']} {record['faction']} influence."
                    )
                else:
                    body_lines.append(
                        f"- {record['display_name']} lacked influence to cover the {record['pledge_amount']} pledge."
                    )
                remaining = record.get("remaining_debt", 0)
                if remaining:
                    body_lines.append(
                        f"  Outstanding debt recorded: {remaining} influence."
                    )
        forfeited_total = sum(
            record.get("deducted", 0)
            for record in penalty_records
            if record["status"] in {"forfeited", "debt"}
        )
        waived_total = sum(1 for record in penalty_records if record["status"] == "waived")
        try:
            self._telemetry.track_game_progression(
                "symposium_penalties",
                float(forfeited_total),
                details={
                    "topic_id": topic_id,
                    "waived": waived_total,
                    "non_voters": len(non_voter_players),
                },
            )
        except Exception:  # pragma: no cover - telemetry optional
            logger.debug("Failed to record symposium penalty telemetry", exc_info=True)
        press = PressRelease(
            type="symposium_resolution",
            headline=f"Symposium Resolved: {topic}",
            body="\n".join(body_lines),
            metadata={
                "topic_id": topic_id,
                "topic": topic,
                "winner": winner,
                "votes": votes,
                "proposal_id": proposal_id,
                "non_voters": non_voters,
                "penalties": penalty_records,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name="The Academy",
            persona_traits=None,
            extra_context={
                "event": "symposium_resolved",
                "topic": topic,
                "winner": winner,
            },
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="symposium_resolved",
                payload={
                    "topic_id": topic_id,
                    "winner": winner,
                    "votes": votes,
                    "proposal_id": proposal_id,
                    "non_voters": non_voters,
                    "penalties": penalty_records,
                },
            )
        )

        layers = self._multi_press.generate_symposium_layers(
            topic,
            description,
            phase="resolution",
            scholars=list(self.state.all_scholars()),
            votes=votes,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={press.type},
            timestamp=now,
            event_type="symposium",
        )

        return press

    # Symposium helpers -------------------------------------------------
    def _initialize_symposium_pledges(self, *, topic_id: int, now: datetime) -> Dict[str, Dict[str, object]]:
        pledges: Dict[str, Dict[str, object]] = {}
        grace_window = timedelta(days=self.settings.symposium_grace_window_days)
        for player in self.state.all_players():
            participation = self.state.get_symposium_participation(player.id)
            participation_data = (
                dict(participation)
                if participation is not None
                else {
                    "player_id": player.id,
                    "miss_streak": 0,
                    "grace_window_start": now,
                    "grace_miss_consumed": 0,
                    "last_voted_at": None,
                }
            )
            grace_start = participation_data.get("grace_window_start")
            if grace_start is None or grace_start + grace_window <= now:
                participation_data["grace_window_start"] = now
                participation_data["grace_miss_consumed"] = 0
            self.state.save_symposium_participation(
                player_id=player.id,
                miss_streak=int(participation_data.get("miss_streak", 0)),
                grace_window_start=participation_data.get("grace_window_start"),
                grace_miss_consumed=int(participation_data.get("grace_miss_consumed", 0)),
                last_voted_at=participation_data.get("last_voted_at"),
                updated_at=now,
            )
            pledge_amount = self._calculate_symposium_pledge(participation_data)
            faction = self._select_pledge_faction(player)
            debt_summary = self._settle_symposium_debts(player, now)
            outstanding_debt = debt_summary.get("outstanding", 0)
            if outstanding_debt > 0:
                debt_penalty = min(
                    outstanding_debt,
                    self.settings.symposium_pledge_escalation_cap,
                )
                pledge_amount += debt_penalty
            else:
                debt_penalty = 0
            self.state.record_symposium_pledge(
                topic_id=topic_id,
                player_id=player.id,
                pledge_amount=pledge_amount,
                faction=faction,
                created_at=now,
            )
            grace_iso = participation_data.get("grace_window_start")
            pledges[player.id] = {
                "display_name": player.display_name,
                "amount": pledge_amount,
                "faction": faction,
                "miss_streak": int(participation_data.get("miss_streak", 0)),
                "grace_miss_consumed": int(participation_data.get("grace_miss_consumed", 0)),
                "grace_window_start": grace_iso.isoformat() if grace_iso else None,
                "outstanding_debt": outstanding_debt,
                "debt_settled": debt_summary.get("settled", 0),
                "debt_penalty": debt_penalty,
                "debts": debt_summary.get("details", []),
                "reprisals": debt_summary.get("reprisals", []),
            }
            if outstanding_debt > 0:
                try:
                    self._telemetry.track_game_progression(
                        "symposium_debt_outstanding",
                        float(outstanding_debt),
                        player_id=player.id,
                        details={"faction": faction or "unknown"},
                    )
                except Exception:  # pragma: no cover
                    logger.debug("Failed to record debt telemetry", exc_info=True)
        return pledges

    def _select_symposium_proposal(
        self,
        now: datetime,
    ) -> Optional[Dict[str, object]]:
        proposals = self.state.list_pending_symposium_proposals(now=now)
        if not proposals:
            self._latest_symposium_scoring = []
            return None
        recent_topics = self.state.list_recent_symposium_topics(
            limit=self.settings.symposium_recent_window
        )
        recent_proposers: Dict[str, datetime] = {}
        for topic in recent_topics:
            proposal_id = topic.get("proposal_id")
            if not proposal_id:
                continue
            proposal_meta = self.state.get_symposium_proposal(proposal_id)
            if not proposal_meta:
                continue
            recent_proposers[proposal_meta["player_id"]] = (
                topic.get("symposium_date") or topic.get("created_at") or now
            )

        scored_entries: List[Dict[str, object]] = []
        best: Optional[Dict[str, object]] = None
        best_score = float("-inf")
        max_age_days = max(1, self.settings.symposium_scoring_max_age_days)
        for proposal in proposals:
            created_at = proposal.get("created_at") or now
            age_days = max(
                0.0,
                (now - created_at).total_seconds() / 86400.0,
            )
            age_decay = max(0.0, (max_age_days - age_days) / max_age_days)
            age_contribution = age_decay * self.settings.symposium_scoring_age_weight
            fresh_bonus = (
                self.settings.symposium_scoring_fresh_bonus
                if proposal["player_id"] not in recent_proposers
                else 0.0
            )
            repeat_penalty = (
                self.settings.symposium_scoring_repeat_penalty
                if proposal["player_id"] in recent_proposers
                else 0.0
            )
            score = age_contribution + fresh_bonus - repeat_penalty
            entry = {
                "proposal_id": proposal["id"],
                "player_id": proposal["player_id"],
                "topic": proposal["topic"],
                "score": score,
                "age_days": age_days,
                "created_at": created_at,
                "age_contribution": age_contribution,
                "fresh_bonus": fresh_bonus,
                "repeat_penalty": repeat_penalty,
                "recent_proposer": proposal["player_id"] in recent_proposers,
            }
            scored_entries.append(entry)
            try:
                self._telemetry.track_game_progression(
                    "symposium_score",
                    float(score),
                    player_id=proposal["player_id"],
                    details={
                        "proposal_id": proposal["id"],
                        "age_days": age_days,
                        "age_contribution": age_contribution,
                        "fresh_bonus": fresh_bonus,
                        "repeat_penalty": repeat_penalty,
                        "recent_proposer": str(proposal["player_id"] in recent_proposers),
                    },
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to record symposium score telemetry", exc_info=True)
            if (
                best is None
                or score > best_score
                or (
                    abs(score - best_score) < 1e-9
                    and created_at < (best.get("created_at") or now)
                )
            ):
                best = proposal
                best_score = score
        scored_entries.sort(key=lambda item: item["score"], reverse=True)
        self._latest_symposium_scoring = scored_entries
        return best

    def _calculate_symposium_pledge(self, participation: Dict[str, object]) -> int:
        base = self.settings.symposium_pledge_base
        cap = self.settings.symposium_pledge_escalation_cap
        miss_streak = int(participation.get("miss_streak", 0))
        escalation = min(max(miss_streak, 0), cap)
        return base + escalation

    def _select_pledge_faction(self, player: Player) -> Optional[str]:
        self._ensure_influence_structure(player)
        positive_balances = [
            (faction, value)
            for faction, value in player.influence.items()
            if value > 0
        ]
        if not positive_balances:
            return None
        faction, _ = max(positive_balances, key=lambda item: item[1])
        return faction

    def _record_symposium_vote_participation(
        self,
        *,
        player_id: str,
        voted_at: datetime,
    ) -> None:
        self.state.save_symposium_participation(
            player_id=player_id,
            miss_streak=0,
            grace_window_start=voted_at,
            grace_miss_consumed=0,
            last_voted_at=voted_at,
            updated_at=voted_at,
        )

    def _handle_symposium_non_voter(
        self,
        *,
        topic_id: int,
        player: Player,
        pledge: Dict[str, object],
        now: datetime,
    ) -> Optional[Dict[str, object]]:
        participation = self.state.get_symposium_participation(player.id) or {
            "miss_streak": 0,
            "grace_window_start": None,
            "grace_miss_consumed": 0,
            "last_voted_at": None,
        }
        grace_window = timedelta(days=self.settings.symposium_grace_window_days)
        grace_start: Optional[datetime] = participation.get("grace_window_start")
        grace_miss_consumed = int(participation.get("grace_miss_consumed", 0))
        if grace_start is None or grace_start + grace_window <= now:
            grace_start = now
            grace_miss_consumed = 0
        miss_streak = int(participation.get("miss_streak", 0)) + 1
        pledge_amount = int(pledge.get("pledge_amount", self.settings.symposium_pledge_base))
        grace_limit = self.settings.symposium_grace_misses

        status = "waived"
        deducted = 0
        faction = pledge.get("faction")
        reason = "grace"
        remaining_debt = 0
        if grace_miss_consumed >= grace_limit:
            penalty_result = self._apply_symposium_penalty(player, pledge_amount)
            deducted = penalty_result["deducted"]
            if penalty_result["faction"]:
                faction = penalty_result["faction"]
            status = "forfeited"
            reason = "insufficient_influence" if deducted == 0 else "penalty"
            if deducted == 0:
                self._queue_admin_notification(
                    f"⚠️ {player.display_name} had insufficient influence to cover a {pledge_amount} pledge."
                )
            if deducted < pledge_amount:
                remaining_debt = pledge_amount - deducted
                debt_faction = faction or self._select_pledge_faction(player) or self._FACTIONS[0]
                self.state.record_symposium_debt(
                    player_id=player.id,
                    faction=debt_faction,
                    amount=remaining_debt,
                    now=now,
                )
                faction = debt_faction
                status = "debt"
        else:
            grace_miss_consumed += 1

        self.state.update_symposium_pledge_status(
            topic_id=topic_id,
            player_id=player.id,
            status=status,
            resolved_at=now,
            faction=faction,
            pledge_amount=pledge_amount,
        )
        self.state.save_symposium_participation(
            player_id=player.id,
            miss_streak=miss_streak,
            grace_window_start=grace_start,
            grace_miss_consumed=grace_miss_consumed,
            last_voted_at=participation.get("last_voted_at"),
            updated_at=now,
        )
        return {
            "player_id": player.id,
            "display_name": player.display_name,
            "status": status,
            "pledge_amount": pledge_amount,
            "deducted": deducted,
            "faction": faction,
            "miss_streak": miss_streak,
            "grace_miss_consumed": grace_miss_consumed,
            "reason": reason,
            "remaining_debt": remaining_debt,
        }

    def _apply_symposium_penalty(self, player: Player, pledge_amount: int) -> Dict[str, object]:
        if pledge_amount <= 0:
            return {"deducted": 0, "faction": None}
        faction = self._select_pledge_faction(player)
        if not faction:
            return {"deducted": 0, "faction": None}
        balance = player.influence.get(faction, 0)
        deducted = min(balance, pledge_amount)
        if deducted <= 0:
            return {"deducted": 0, "faction": faction}
        self._apply_influence_change(player, faction, -deducted)
        self.state.upsert_player(player)
        return {"deducted": deducted, "faction": faction}

    def _apply_influence_debt_reprisal(
        self,
        *,
        player: Player,
        debt_details: List[Dict[str, object]],
        now: datetime,
        source: str,
        threshold: int,
        penalty: int,
        cooldown_days: int,
        telemetry_event: str,
    ) -> List[Dict[str, object]]:
        if threshold <= 0 or penalty < 0:
            return []
        cooldown = timedelta(days=cooldown_days)
        reprisals: List[Dict[str, object]] = []
        for debt in debt_details:
            remaining = debt.get("remaining", 0)
            if remaining < threshold:
                continue
            faction = debt.get("faction")
            if not faction:
                continue
            debt_record = self.state.get_influence_debt_record(
                player_id=player.id,
                faction=faction,
                source=source,
            )
            if not debt_record or debt_record.get("source") != source:
                continue
            last_reprisal = debt_record.get("last_reprisal_at")
            if isinstance(last_reprisal, datetime) and last_reprisal + cooldown > now:
                continue
            influence_before = player.influence.get(faction, 0)
            penalty_applied = min(influence_before, penalty)
            reputation_penalty = 0
            if penalty_applied > 0:
                self._apply_influence_change(player, faction, -penalty_applied)
                self.state.upsert_player(player)
            else:
                reputation_penalty = 1
                player.adjust_reputation(
                    -reputation_penalty,
                    self.settings.reputation_bounds["min"],
                    self.settings.reputation_bounds["max"],
                )
                self.state.upsert_player(player)
            reprisal_level = (debt_record.get("reprisal_level", 0) + 1)
            self.state.update_influence_debt_reprisal(
                player_id=player.id,
                faction=faction,
                reprisal_level=reprisal_level,
                now=now,
                source=source,
            )
            message = {
                "player_id": player.id,
                "display_name": player.display_name,
                "faction": faction,
                "penalty_influence": penalty_applied,
                "penalty_reputation": reputation_penalty,
                "reprisal_level": reprisal_level,
                "remaining": remaining,
            }
            if isinstance(last_reprisal, datetime):
                message["last_reprisal_at"] = last_reprisal.isoformat()
            elif last_reprisal:
                message["last_reprisal_at"] = str(last_reprisal)
            reprisals.append(message)
            try:
                self._telemetry.track_game_progression(
                    telemetry_event,
                    float(penalty_applied or -reputation_penalty),
                    player_id=player.id,
                    details={
                        "faction": faction,
                        "reprisal_level": reprisal_level,
                        "remaining": remaining,
                        "source": source,
                    },
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to record debt reprisal telemetry", exc_info=True)

            resolve_at = now
            self.state.schedule_followup(
                player.id,
                "symposium_reprimand",
                resolve_at,
                {
                    "player_id": player.id,
                    "display_name": player.display_name,
                    "faction": faction,
                    "penalty_influence": penalty_applied,
                    "penalty_reputation": reputation_penalty,
                    "reprisal_level": reprisal_level,
                    "remaining": remaining,
                },
            )
            self._queue_admin_notification(
                (
                    "🛡️ Symposium reprisal: {name} owes {remaining} influence to {faction} "
                    "(reprisal level {level}, penalty {penalty})"
                ).format(
                    name=player.display_name,
                    remaining=remaining,
                    faction=faction,
                    level=reprisal_level,
                    penalty=penalty_applied or reputation_penalty,
                )
            )
        return reprisals

    def _settle_symposium_debts(
        self,
        player: Player,
        now: datetime,
    ) -> Dict[str, object]:
        debts = self.state.list_symposium_debts(player.id)
        if not debts:
            return {"settled": 0, "outstanding": 0, "details": []}
        settled_total = 0
        outstanding_total = 0
        updated = False
        details: List[Dict[str, object]] = []
        reprisal_events: List[Dict[str, object]] = []
        for debt in debts:
            faction = debt["faction"]
            amount = int(debt["amount"])
            balance = player.influence.get(faction, 0)
            payment = min(balance, amount)
            if payment > 0:
                self._apply_influence_change(player, faction, -payment)
                self.state.apply_symposium_debt_payment(
                    player_id=player.id,
                    faction=faction,
                    amount=payment,
                    now=now,
                )
                settled_total += payment
                amount -= payment
                updated = True
            if amount > 0:
                outstanding_total += amount
            details.append(
                {
                    "faction": faction,
                    "remaining": amount,
                    "reprisal_level": debt.get("reprisal_level", 0),
                    "last_reprisal_at": (
                        debt.get("last_reprisal_at").isoformat()
                        if isinstance(debt.get("last_reprisal_at"), datetime)
                        else debt.get("last_reprisal_at")
                    ),
                }
            )
        if updated:
            self.state.upsert_player(player)
        if details:
            reprisal_events = self._apply_influence_debt_reprisal(
                player=player,
                debt_details=details,
                now=now,
                source="symposium",
                threshold=self.settings.symposium_debt_reprisal_threshold,
                penalty=self.settings.symposium_debt_reprisal_penalty,
                cooldown_days=self.settings.symposium_debt_reprisal_cooldown_days,
                telemetry_event="symposium_debt_reprisal",
            )
            for detail in details:
                record = self.state.get_symposium_debt_record(
                    player_id=player.id,
                    faction=detail["faction"],
                )
                if record:
                    detail["reprisal_level"] = record.get("reprisal_level", 0)
                    last_reprisal = record.get("last_reprisal_at")
                    if isinstance(last_reprisal, datetime):
                        detail["last_reprisal_at"] = last_reprisal.isoformat()
                    else:
                        detail["last_reprisal_at"] = last_reprisal
        return {
            "settled": settled_total,
            "outstanding": outstanding_total,
            "details": details,
            "reprisals": reprisal_events,
        }

    def _contract_commitments(self) -> Dict[str, Dict[str, int]]:
        commitments: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for scholar in self.state.all_scholars():
            contract = getattr(scholar, "contract", {}) or {}
            employer = contract.get("employer")
            faction = contract.get("faction")
            if employer and faction:
                commitments[employer][faction] += 1
        return {player: dict(factions) for player, factions in commitments.items()}

    def _apply_contract_upkeep(self, now: datetime) -> None:
        upkeep = max(0, self.settings.contract_upkeep_per_scholar)
        if upkeep == 0:
            return
        commitments = self._contract_commitments()
        if not commitments:
            return
        for player_id, faction_counts in commitments.items():
            player = self.state.get_player(player_id)
            if not player:
                continue
            debt_details: List[Dict[str, object]] = []
            for faction, count in faction_counts.items():
                total_cost = upkeep * count
                if total_cost <= 0:
                    continue
                self._ensure_influence_structure(player)
                available = player.influence.get(faction, 0)
                existing_record = self.state.get_influence_debt_record(
                    player_id=player_id,
                    faction=faction,
                    source="contract",
                )
                existing_debt = existing_record.get("amount", 0) if existing_record else 0
                paid_toward_debt = 0
                if existing_debt and available > 0:
                    paid_toward_debt = min(available, existing_debt)
                    available -= paid_toward_debt
                    self.state.apply_influence_debt_payment(
                        player_id=player_id,
                        faction=faction,
                        amount=paid_toward_debt,
                        now=now,
                        source="contract",
                    )
                    self._apply_influence_change(player, faction, -paid_toward_debt)

                payment_for_current = min(available, total_cost)
                if payment_for_current > 0:
                    self._apply_influence_change(player, faction, -payment_for_current)
                    available -= payment_for_current
                debt = total_cost - payment_for_current
                if debt > 0:
                    self.state.record_influence_debt(
                        player_id=player_id,
                        faction=faction,
                        amount=debt,
                        now=now,
                        source="contract",
                    )
                    self._queue_admin_notification(
                        f"⚖️ Contract upkeep shortfall: {player.display_name} owes {debt} {faction} influence."
                    )
                record = self.state.get_influence_debt_record(
                    player_id=player_id,
                    faction=faction,
                    source="contract",
                )
                remaining = record.get("amount", 0) if record else 0
                reprisal_level = record.get("reprisal_level", 0) if record else 0
                last_reprisal = record.get("last_reprisal_at") if record else None
                debt_details.append(
                    {
                        "faction": faction,
                        "remaining": remaining,
                        "reprisal_level": reprisal_level,
                        "last_reprisal_at": last_reprisal.isoformat()
                        if isinstance(last_reprisal, datetime)
                        else last_reprisal,
                    }
                )
                try:
                    self._telemetry.track_game_progression(
                        "contract_upkeep",
                        float(total_cost),
                        player_id=player_id,
                        details={
                            "faction": faction,
                            "paid": payment_for_current + paid_toward_debt,
                            "debt": debt,
                            "contracts": count,
                        },
                    )
                except Exception:  # pragma: no cover
                    logger.debug("Failed to record contract upkeep telemetry", exc_info=True)
            self.state.upsert_player(player)
            if debt_details:
                reprisal_events = self._apply_influence_debt_reprisal(
                    player=player,
                    debt_details=debt_details,
                    now=now,
                    source="contract",
                    threshold=self.settings.contract_debt_reprisal_threshold,
                    penalty=self.settings.contract_debt_reprisal_penalty,
                    cooldown_days=self.settings.contract_debt_reprisal_cooldown_days,
                    telemetry_event="contract_debt_reprisal",
                )
                for detail in debt_details:
                    record = self.state.get_influence_debt_record(
                        player_id=player.id,
                        faction=detail["faction"],
                        source="contract",
                    )
                    if record:
                        detail["reprisal_level"] = record.get("reprisal_level", 0)
                        last_reprisal = record.get("last_reprisal_at")
                        if isinstance(last_reprisal, datetime):
                            detail["last_reprisal_at"] = last_reprisal.isoformat()
                        else:
                            detail["last_reprisal_at"] = last_reprisal
                if reprisal_events:
                    for event in reprisal_events:
                        if event.get("penalty_influence"):
                            note = (
                                f"⚖️ Contract reprisal: {event['display_name']} loses {event['penalty_influence']} "
                                f"{event['faction']} influence for unpaid upkeep."
                            )
                        else:
                            note = (
                                f"⚠️ Contract reprisal: {event['display_name']} takes a reputation hit for "
                                f"unpaid upkeep ({event['faction']})."
                            )
                        self._queue_admin_notification(note)

    def _apply_seasonal_commitments(self, now: datetime) -> List[PressRelease]:
        releases: List[PressRelease] = []
        commitments = self.state.list_active_seasonal_commitments(now)
        if not commitments:
            return releases

        for commitment in commitments:
            last_processed = commitment.get("last_processed_at")
            if last_processed and (now - last_processed) < timedelta(hours=6):
                continue

            player = self.state.get_player(commitment["player_id"])
            if not player:
                continue

            faction = commitment.get("faction", "")
            relationship = self._player_faction_relationship(
                player,
                faction,
                weight=self.settings.seasonal_commitment_relationship_weight,
            )
            base_cost = int(commitment.get("base_cost", self.settings.seasonal_commitment_base_cost))
            modifier = max(0.5, 1.0 - relationship)
            effective_cost = max(0, int(round(base_cost * modifier)))

            self._ensure_influence_structure(player)
            available = player.influence.get(faction, 0)
            paid = min(available, effective_cost)
            if paid:
                self._apply_influence_change(player, faction, -paid)
            debt = effective_cost - paid
            debt_details: List[Dict[str, object]] = []
            if debt > 0:
                self.state.record_influence_debt(
                    player_id=player.id,
                    faction=faction,
                    amount=debt,
                    now=now,
                    source="seasonal",
                )

            debt_record = self.state.get_influence_debt_record(
                player_id=player.id,
                faction=faction,
                source="seasonal",
            )
            if debt_record and debt_record.get("amount", 0) > 0:
                debt_details.append(
                    {
                        "faction": faction,
                        "remaining": int(debt_record.get("amount", 0)),
                        "reprisal_level": int(debt_record.get("reprisal_level", 0)),
                        "last_reprisal_at": debt_record.get("last_reprisal_at"),
                    }
                )
            self.state.upsert_player(player)

            if debt_details:
                self._apply_influence_debt_reprisal(
                    player=player,
                    debt_details=debt_details,
                    now=now,
                    source="seasonal",
                    threshold=self.settings.seasonal_commitment_reprisal_threshold,
                    penalty=self.settings.seasonal_commitment_reprisal_penalty,
                    cooldown_days=self.settings.seasonal_commitment_reprisal_cooldown_days,
                    telemetry_event="seasonal_commitment_reprisal",
                )

            ctx = SeasonalCommitmentContext(
                player=player.display_name,
                faction=faction or "Unaligned",
                tier=commitment.get("tier"),
                cost=effective_cost,
                relationship_modifier=relationship,
                debt=debt,
                status="active",
                paid=paid,
            )
            release = seasonal_commitment_update(ctx)
            release.metadata.setdefault("commitment", {}).update(
                {
                    "id": commitment.get("id"),
                    "tier": commitment.get("tier"),
                    "base_cost": base_cost,
                    "relationship_modifier": relationship,
                    "paid": paid,
                    "debt": int(debt_record.get("amount", 0)) if debt_record else debt,
                }
            )
            self._archive_press(release, now)
            releases.append(release)

            self.state.mark_seasonal_commitment_processed(commitment["id"], now)

            end_at = commitment.get("end_at")
            if isinstance(end_at, datetime) and end_at <= now:
                self.state.set_seasonal_commitment_status(
                    commitment_id=commitment["id"],
                    status="completed",
                    processed_at=now,
                )
                completion_release = seasonal_commitment_complete(
                    SeasonalCommitmentContext(
                        player=player.display_name,
                        faction=faction or "Unaligned",
                        tier=commitment.get("tier"),
                        cost=effective_cost,
                        relationship_modifier=relationship,
                        debt=debt,
                        status="completed",
                        paid=paid,
                    )
                )
                completion_release.metadata.setdefault("commitment", {}).update(
                    {
                        "id": commitment.get("id"),
                        "completed_at": now.isoformat(),
                    }
                )
                self._archive_press(completion_release, now)
                releases.append(completion_release)

            try:
                self._telemetry.track_game_progression(
                    "seasonal_commitment_charge",
                    float(effective_cost),
                    player_id=player.id,
                    details={
                        "faction": faction,
                        "relationship_modifier": relationship,
                        "debt": debt,
                    },
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to record seasonal commitment telemetry", exc_info=True)

        return releases

    def _contract_summary_for_player(self, player: Player) -> Dict[str, Dict[str, object]]:
        commitments = self._contract_commitments().get(player.id, {})
        summary: Dict[str, Dict[str, object]] = {}
        for faction, count in commitments.items():
            total_cost = count * self.settings.contract_upkeep_per_scholar
            debt_record = self.state.get_influence_debt_record(
                player_id=player.id,
                faction=faction,
                source="contract",
            )
            outstanding = (
                debt_record.get("amount", 0)
                if debt_record and debt_record.get("source") == "contract"
                else 0
            )
            summary[faction] = {
                "scholars": count,
                "upkeep": total_cost,
                "outstanding": outstanding,
            }
        return summary

    # Admin tools ---------------------------------------------------
    def admin_adjust_reputation(
        self,
        admin_id: str,
        player_id: str,
        delta: int,
        reason: str,
    ) -> PressRelease:
        """Admin command to adjust a player's reputation."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        old_reputation = player.reputation
        player.adjust_reputation(
            delta,
            self.settings.reputation_bounds["min"],
            self.settings.reputation_bounds["max"],
        )
        self.state.upsert_player(player)

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline="Administrative Reputation Adjustment",
            body=(
                f"Player {player.display_name}'s reputation adjusted by {delta:+d} "
                f"(from {old_reputation} to {player.reputation})\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}"
            ),
            metadata={
                "admin": admin_id,
                "player": player_id,
                "delta": delta,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_adjust_reputation",
                "player": player.display_name,
                "delta": delta,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_reputation_adjustment",
                payload={
                    "admin": admin_id,
                    "player": player_id,
                    "delta": delta,
                    "old": old_reputation,
                    "new": player.reputation,
                    "reason": reason,
                },
            )
        )

        return press

    def admin_adjust_influence(
        self,
        admin_id: str,
        player_id: str,
        faction: str,
        delta: int,
        reason: str,
    ) -> PressRelease:
        """Admin command to adjust a player's influence."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")

        if faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {faction}")

        self._ensure_influence_structure(player)
        old_influence = player.influence.get(faction, 0)

        # Direct adjustment for admin, bypassing soft caps
        player.influence[faction] = max(0, player.influence.get(faction, 0) + delta)
        self.state.upsert_player(player)

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline="Administrative Influence Adjustment",
            body=(
                f"Player {player.display_name}'s {faction} influence adjusted by {delta:+d} "
                f"(from {old_influence} to {player.influence[faction]})\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}"
            ),
            metadata={
                "admin": admin_id,
                "player": player_id,
                "faction": faction,
                "delta": delta,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_adjust_influence",
                "player": player.display_name,
                "faction": faction,
                "delta": delta,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_influence_adjustment",
                payload={
                    "admin": admin_id,
                    "player": player_id,
                    "faction": faction,
                    "delta": delta,
                    "old": old_influence,
                    "new": player.influence[faction],
                    "reason": reason,
                },
            )
        )

        return press

    def admin_force_defection(
        self,
        admin_id: str,
        scholar_id: str,
        new_faction: str,
        reason: str,
    ) -> PressRelease:
        """Admin command to force a scholar defection."""
        self._ensure_not_paused()
        scholar = self.state.get_scholar(scholar_id)
        if not scholar:
            raise ValueError(f"Scholar {scholar_id} not found")

        old_faction = scholar.contract.get("employer", "Unknown")

        # Force the defection
        defection_triggered, press = self.evaluate_defection_offer(
            scholar_id=scholar_id,
            offer_quality=10.0,  # Maximum quality to guarantee defection
            mistreatment=0.0,
            alignment=1.0,
            plateau=0.0,
            new_faction=new_faction,
        )

        # Add admin note to the press release
        admin_press = PressRelease(
            type="admin_action",
            headline="Administrative Defection Order",
            body=(
                f"Scholar {scholar.name} has been ordered to defect from {old_faction} to {new_faction}\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}\n\n"
                f"Original Press:\n{press.body}"
            ),
            metadata={
                "admin": admin_id,
                "scholar": scholar_id,
                "old_faction": old_faction,
                "new_faction": new_faction,
                "reason": reason,
            },
        )
        admin_press = self._enhance_press_release(
            admin_press,
            base_body=admin_press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_force_defection",
                "scholar": scholar.name,
                "new_faction": new_faction,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(admin_press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_force_defection",
                payload={
                    "admin": admin_id,
                    "scholar": scholar_id,
                    "new_faction": new_faction,
                    "reason": reason,
                },
            )
        )

        return admin_press

    def admin_cancel_expedition(
        self,
        admin_id: str,
        expedition_code: str,
        reason: str,
    ) -> PressRelease:
        """Admin command to cancel a pending expedition."""
        self._ensure_not_paused()
        # Check if expedition exists in pending expeditions
        if expedition_code not in self._pending_expeditions:
            raise ValueError(f"Expedition {expedition_code} not found or already resolved")

        expedition = self._pending_expeditions[expedition_code]

        # Remove from pending expeditions
        del self._pending_expeditions[expedition_code]

        # Record cancellation in database
        self.state.record_expedition(
            ExpeditionRecord(
                code=expedition_code,
                timestamp=datetime.now(timezone.utc),
                player_id=expedition.player_id,
                expedition_type=expedition.expedition_type,
                objective=expedition.objective,
                team=expedition.team,
                funding=expedition.funding,
                prep_depth=expedition.prep_depth,
                confidence=expedition.confidence.value,
                outcome=ExpeditionOutcome.FAILURE,
                reputation_delta=0,
            ),
            result_payload={"cancelled": True, "admin": admin_id, "reason": reason},
        )

        # Generate press release
        press = PressRelease(
            type="admin_action",
            headline="Expedition Cancelled by Administration",
            body=(
                f"Expedition {expedition_code} has been cancelled\n"
                f"Reason: {reason}\n"
                f"Admin: {admin_id}\n"
                f"No reputation changes will be applied."
            ),
            metadata={
                "admin": admin_id,
                "expedition_code": expedition_code,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_cancel_expedition",
                "expedition_code": expedition_code,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_cancel_expedition",
                payload={
                    "admin": admin_id,
                    "expedition_code": expedition_code,
                    "reason": reason,
                },
            )
        )

        return press

    def admin_create_seasonal_commitment(
        self,
        admin_id: str,
        player_id: str,
        faction: str,
        *,
        tier: Optional[str] = None,
        base_cost: Optional[int] = None,
        duration_days: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> PressRelease:
        """Create a seasonal commitment on behalf of a player."""
        self._ensure_not_paused()
        player = self.state.get_player(player_id)
        if not player:
            raise ValueError(f"Player {player_id} not found")
        if faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {faction}")

        commitment_id = self.start_seasonal_commitment(
            player_id=player_id,
            faction=faction,
            tier=tier,
            base_cost=base_cost,
            duration_days=duration_days,
            allow_override=True,
        )

        record = self.state.get_seasonal_commitment(commitment_id)
        if record is None:
            raise ValueError("Failed to persist seasonal commitment")

        duration = max(1, (record["end_at"] - record["start_at"]).days)
        summary_reason = f"\nReason: {reason}" if reason else ""
        press = PressRelease(
            type="admin_action",
            headline="Seasonal Commitment Established",
            body=(
                f"Admin {admin_id} registered a seasonal pledge for {player.display_name}.\n"
                f"Faction: {faction.title()}  Tier: {record.get('tier') or 'Unspecified'}\n"
                f"Base cost: {record.get('base_cost')}  Duration: {duration} days{summary_reason}"
            ),
            metadata={
                "admin": admin_id,
                "player": player_id,
                "faction": faction,
                "tier": record.get("tier"),
                "commitment_id": commitment_id,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_create_seasonal_commitment",
                "player": player.display_name,
                "faction": faction,
                "commitment": commitment_id,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_create_seasonal_commitment",
                payload={
                    "admin": admin_id,
                    "player": player_id,
                    "faction": faction,
                    "tier": record.get("tier"),
                    "commitment_id": commitment_id,
                    "reason": reason,
                },
            )
        )

        self._queue_admin_notification(
            f"📝 {admin_id} created seasonal commitment #{commitment_id} for {player.display_name}"
        )
        return press

    def admin_update_seasonal_commitment(
        self,
        admin_id: str,
        commitment_id: int,
        *,
        status: str,
        reason: Optional[str] = None,
    ) -> PressRelease:
        """Cancel or complete an existing seasonal commitment."""
        self._ensure_not_paused()
        record = self.state.get_seasonal_commitment(commitment_id)
        if record is None:
            raise ValueError(f"Commitment {commitment_id} not found")

        if status not in {"completed", "cancelled"}:
            raise ValueError("Status must be 'completed' or 'cancelled'")

        now = datetime.now(timezone.utc)
        self.state.set_seasonal_commitment_status(commitment_id, status, now)

        player = self.state.get_player(record["player_id"])
        player_name = player.display_name if player else record["player_id"]
        summary_reason = f"\nReason: {reason}" if reason else ""
        press = PressRelease(
            type="admin_action",
            headline=f"Seasonal Commitment {status.title()}",
            body=(
                f"Admin {admin_id} marked seasonal commitment #{commitment_id} as {status}.\n"
                f"Player: {player_name}  Faction: {record.get('faction') or 'Unaligned'}{summary_reason}"
            ),
            metadata={
                "admin": admin_id,
                "commitment_id": commitment_id,
                "status": status,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_update_seasonal_commitment",
                "commitment": commitment_id,
                "status": status,
            },
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_update_seasonal_commitment",
                payload={
                    "admin": admin_id,
                    "commitment_id": commitment_id,
                    "status": status,
                    "reason": reason,
                },
            )
        )

        self._queue_admin_notification(
            f"⚙️ {admin_id} marked seasonal commitment #{commitment_id} as {status}"
        )
        return press

    def admin_create_faction_project(
        self,
        admin_id: str,
        name: str,
        faction: str,
        *,
        target_progress: float,
        metadata: Optional[Dict[str, object]] = None,
        reason: Optional[str] = None,
    ) -> PressRelease:
        """Create a faction project via admin tooling."""
        self._ensure_not_paused()
        if faction not in self._FACTIONS:
            raise ValueError(f"Invalid faction: {faction}")

        project_id = self.start_faction_project(
            name=name,
            faction=faction,
            target_progress=target_progress,
            metadata=metadata,
        )
        record = self.state.get_faction_project(project_id)
        if record is None:
            raise ValueError("Failed to persist faction project")

        summary_reason = f"\nReason: {reason}" if reason else ""
        press = PressRelease(
            type="admin_action",
            headline="Faction Project Initiated",
            body=(
                f"Admin {admin_id} initiated project '{name}' for {faction.title()}.\n"
                f"Target progress: {target_progress}{summary_reason}"
            ),
            metadata={
                "admin": admin_id,
                "project_id": project_id,
                "name": name,
                "faction": faction,
                "target_progress": target_progress,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_create_faction_project",
                "project": project_id,
                "faction": faction,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_create_faction_project",
                payload={
                    "admin": admin_id,
                    "project_id": project_id,
                    "name": name,
                    "faction": faction,
                    "target_progress": target_progress,
                    "reason": reason,
                },
            )
        )

        self._queue_admin_notification(
            f"🏗️ {admin_id} created faction project #{project_id} ({name})"
        )
        return press

    def admin_update_faction_project(
        self,
        admin_id: str,
        project_id: int,
        *,
        status: str,
        reason: Optional[str] = None,
    ) -> PressRelease:
        """Cancel or complete a faction project via admin tooling."""
        self._ensure_not_paused()
        record = self.state.get_faction_project(project_id)
        if record is None:
            raise ValueError(f"Faction project {project_id} not found")

        if status not in {"completed", "cancelled"}:
            raise ValueError("Status must be 'completed' or 'cancelled'")

        now = datetime.now(timezone.utc)
        if status == "completed":
            self.state.complete_faction_project(project_id, now)
        else:
            self.state.set_faction_project_status(project_id, status, now)

        summary_reason = f"\nReason: {reason}" if reason else ""
        press = PressRelease(
            type="admin_action",
            headline=f"Faction Project {status.title()}",
            body=(
                f"Admin {admin_id} marked faction project #{project_id} ({record['name']}) as {status}."
                f"\nFaction: {record.get('faction') or 'Unaligned'}{summary_reason}"
            ),
            metadata={
                "admin": admin_id,
                "project_id": project_id,
                "status": status,
                "reason": reason,
            },
        )
        press = self._enhance_press_release(
            press,
            base_body=press.body,
            persona_name=admin_id,
            persona_traits=None,
            extra_context={
                "event": "admin_update_faction_project",
                "project": project_id,
                "status": status,
            },
        )

        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_update_faction_project",
                payload={
                    "admin": admin_id,
                    "project_id": project_id,
                    "status": status,
                    "reason": reason,
                },
            )
        )

        self._queue_admin_notification(
            f"📦 {admin_id} marked faction project #{project_id} as {status}"
        )
        return press

    def admin_list_orders(
        self,
        *,
        order_type: str | None = None,
        status: str | None = "pending",
        limit: int = 15,
    ) -> List[Dict[str, object]]:
        """Return dispatcher orders for moderator review."""

        limit = max(1, min(limit, 50))
        orders = self.state.list_orders(order_type=order_type, status=status)
        trimmed = orders[:limit]
        summaries: List[Dict[str, object]] = []
        for order in trimmed:
            summaries.append(
                {
                    "id": order["id"],
                    "order_type": order.get("order_type"),
                    "status": order.get("status"),
                    "actor_id": order.get("actor_id"),
                    "subject_id": order.get("subject_id"),
                    "scheduled_at": (
                        order.get("scheduled_at").isoformat()
                        if isinstance(order.get("scheduled_at"), datetime)
                        else None
                    ),
                    "created_at": (
                        order.get("created_at").isoformat()
                        if isinstance(order.get("created_at"), datetime)
                        else None
                    ),
                    "payload": order.get("payload", {}),
                }
            )
        return summaries

    def admin_cancel_order(
        self,
        *,
        order_id: int,
        reason: str | None = None,
    ) -> Dict[str, object]:
        """Cancel a dispatcher order via moderator action."""

        order = self.state.get_order(order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        status = order.get("status")
        if status != "pending":
            raise ValueError(f"Order {order_id} is not pending (status: {status})")

        updated = self.state.update_order_status(
            order_id,
            "cancelled",
            result={"reason": reason} if reason else None,
        )
        if not updated:
            raise ValueError(f"Failed to cancel order {order_id}")

        summary = {
            "id": order_id,
            "order_type": order.get("order_type"),
            "actor_id": order.get("actor_id"),
            "subject_id": order.get("subject_id"),
            "reason": reason,
        }

        notice = (
            f"🧾 Cancelled order #{order_id} ({summary['order_type']})"
            + (f" – {reason}" if reason else "")
        )
        self._queue_admin_notification(notice)
        now = datetime.now(timezone.utc)
        self.state.append_event(
            Event(
                timestamp=now,
                action="admin_cancel_order",
                payload={**summary, "timestamp": now.isoformat()},
            )
        )
        try:
            self._telemetry.track_system_event(
                "dispatcher_order_cancelled",
                source="admin",
                reason=notice,
            )
        except Exception:  # pragma: no cover
            logger.debug("Failed to record order cancellation telemetry", exc_info=True)

        return summary

    def resume_game(self, admin_id: Optional[str] = None) -> PressRelease:
        """Resume the game after a pause."""

        actor = admin_id or "system"
        with self._llm_lock:
            was_paused = self._paused
            previous_reason = self._pause_reason
            self._paused = False
            self._pause_reason = None
            self._pause_source = None
            self._llm_fail_start = None

        message = (
            f"✅ Game resumed by {actor}."
            if was_paused
            else f"ℹ️ Resume requested by {actor}; game was not paused."
        )
        self._queue_admin_notification(message)

        body_lines = [message]
        if previous_reason:
            body_lines.append(f"Previous pause reason: {previous_reason}")

        press = PressRelease(
            type="admin_action",
            headline="Game Resume",
            body="\n".join(body_lines),
            metadata={
                "admin": actor,
                "previous_reason": previous_reason,
                "was_paused": was_paused,
            },
        )

        now = datetime.now(timezone.utc)
        self._archive_press(press, now)
        self.state.append_event(
            Event(
                timestamp=now,
                action="game_resumed",
                payload={
                    "admin": actor,
                    "was_paused": was_paused,
                    "previous_reason": previous_reason,
                },
            )
        )

        layers = self._multi_press.generate_admin_layers(
            event="resume",
            actor=actor,
            reason=previous_reason,
        )
        self._apply_multi_press_layers(
            layers,
            skip_types={press.type},
            timestamp=now,
            event_type="admin",
        )

        return press

    def wager_reference(self) -> Dict[str, object]:
        """Expose wager tuning, thresholds, and reputation bounds for UX surfaces."""

        wagers: Dict[str, Dict[str, object]] = {}
        for level in ConfidenceLevel:
            config = self.settings.confidence_wagers.get(level.value, {})
            wagers[level.value] = {
                "reward": int(config.get("reward", 0)),
                "penalty": int(config.get("penalty", 0)),
                "triggers_recruitment_cooldown": level is ConfidenceLevel.STAKE_CAREER,
            }
        bounds = self.settings.reputation_bounds
        return {
            "wagers": wagers,
            "action_thresholds": dict(self.settings.action_thresholds),
            "reputation_bounds": {
                "min": int(bounds.get("min", 0)),
                "max": int(bounds.get("max", 0)),
            },
        }

    def export_press_archive(self, limit: int = 10, offset: int = 0) -> List[PressRecord]:
        return self.state.list_press_releases(limit=limit, offset=offset)

    def export_log(self, limit: int = 20) -> Dict[str, Iterable[object]]:
        events = self.state.export_events()
        press = self.state.list_press_releases(limit=limit)
        return {"events": events[-limit:], "press": press}

    def export_web_archive(
        self,
        output_dir: Path | None = None,
        *,
        source: str = "manual",
    ) -> Path:
        """Export the complete game history as a static web archive.

        Args:
            output_dir: Directory to export to. Defaults to ./web_archive

        Returns:
            Path to the exported archive directory
        """
        from .web_archive import WebArchive

        if output_dir is None:
            output_dir = Path("web_archive")

        base_url = os.getenv("GREAT_WORK_ARCHIVE_BASE_URL")

        archive = WebArchive(self.state, output_dir, base_url=base_url)
        result = archive.export_full_archive()
        try:
            self._telemetry.track_system_event(
                "web_archive_export",
                source=source,
                reason=str(result),
            )
        except Exception:
            logger.debug("Telemetry tracking for web archive export failed", exc_info=True)
        return result

    def advance_digest(self) -> List[PressRelease]:
        """Advance the digest tick, decaying cooldowns and maintaining the roster."""

        self._ensure_not_paused()
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        expired_ids = self.state.expire_symposium_proposals(now)
        if expired_ids:
            self._queue_admin_notification(
                f"🗂️ Expired {len(expired_ids)} symposium proposal(s) during digest."
            )
        releases.extend(self.release_scheduled_press(now))
        years_elapsed, current_year = self.state.advance_timeline(
            now, self.settings.time_scale_days_per_year
        )
        if years_elapsed:
            timeline_press = PressRelease(
                type="timeline_update",
                headline=f"The year turns to {current_year}",
                body=(
                    "The Gazette notes the turning of the year. "
                    f"{years_elapsed} year(s) slip into history and the calendar now reads {current_year}."
                ),
                metadata={
                    "current_year": current_year,
                    "years_elapsed": years_elapsed,
                },
            )
            self._archive_press(timeline_press, now)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="timeline_advanced",
                    payload={
                        "current_year": current_year,
                        "years_elapsed": years_elapsed,
                    },
                )
            )
            releases.append(timeline_press)
        for player in list(self.state.all_players()):
            player.tick_cooldowns()
            self.state.upsert_player(player)
        self._ensure_roster()
        releases.extend(self._progress_careers())
        releases.extend(self._resolve_followups())
        releases.extend(self._process_symposium_reminders())
        self._apply_contract_upkeep(now)
        releases.extend(self._apply_seasonal_commitments(now))
        releases.extend(self._advance_faction_projects(now))
        releases.extend(self.resolve_conferences())
        return releases

    def _confidence_delta(self, confidence: ConfidenceLevel, outcome: ExpeditionOutcome) -> int:
        wagers = self.settings.confidence_wagers
        table = wagers[confidence.value]
        success_states = {ExpeditionOutcome.SUCCESS, ExpeditionOutcome.LANDMARK}
        if outcome in success_states:
            return table["reward"]
        if outcome == ExpeditionOutcome.PARTIAL:
            return max(1, table["reward"] // 2)
        return table["penalty"]

    # Internal helpers --------------------------------------------------
    def _archive_press(self, press: PressRelease, timestamp: datetime) -> None:
        self.state.record_press_release(PressRecord(timestamp=timestamp, release=press))

    def _initial_generated_counter(self) -> int:
        max_index = 0
        for scholar in self.state.all_scholars():
            if scholar.id.startswith("s.proc-"):
                try:
                    _, value = scholar.id.split("proc-")
                    max_index = max(max_index, int(value))
                except ValueError:
                    continue
        return max_index + 1

    def _ensure_roster(self) -> None:
        scholars = list(self.state.all_scholars())
        while len(scholars) < self._MIN_SCHOLAR_ROSTER:
            identifier = f"s.proc-{self._generated_counter:03d}"
            self._generated_counter += 1
            scholar = self.repository.generate(self._rng, identifier)
            self.state.save_scholar(scholar)
            scholars.append(scholar)
            self.state.append_event(
                Event(
                    timestamp=datetime.now(timezone.utc),
                    action="scholar_spawned",
                    payload={"id": scholar.id, "name": scholar.name, "origin": "roster_fill"},
                )
            )
        if len(scholars) <= self._MAX_SCHOLAR_ROSTER:
            return
        surplus = len(scholars) - self._MAX_SCHOLAR_ROSTER
        ranked = sorted(
            scholars,
            key=lambda s: (
                0 if s.contract.get("employer") == "Independent" else 1,
                s.stats.loyalty,
                len(s.memory.facts),
            ),
        )
        for scholar in ranked[:surplus]:
            self.state.remove_scholar(scholar.id)
            self.state.append_event(
                Event(
                    timestamp=datetime.now(timezone.utc),
                    action="scholar_retired",
                    payload={"id": scholar.id, "name": scholar.name},
                )
            )

    def _progress_careers(self) -> List[PressRelease]:
        """Progress careers only for scholars with active mentorships."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)

        # First resolve pending mentorships
        releases.extend(self._resolve_mentorships())

        for scholar in list(self.state.all_scholars()):
            # Check if scholar has an active mentorship
            mentorship = self.state.get_active_mentorship(scholar.id)
            if not mentorship:
                continue  # No mentor, no progression

            track = scholar.career.get("track", "Academia")
            ladder = self._CAREER_TRACKS.get(track, self._CAREER_TRACKS["Academia"])
            tier = scholar.career.get("tier", ladder[0])
            ticks = int(scholar.career.get("ticks", 0)) + 1
            scholar.career["ticks"] = ticks
            if tier not in ladder:
                ladder = self._CAREER_TRACKS["Academia"]
                tier = ladder[0]
                scholar.career["tier"] = tier
            idx = ladder.index(tier)
            if idx < len(ladder) - 1 and ticks >= self._CAREER_TICKS_REQUIRED:
                scholar.career["tier"] = ladder[idx + 1]
                scholar.career["ticks"] = 0

                # Get mentor's name for the press release
                mentor_player = self.state.get_player(mentorship[1])
                mentor_name = mentor_player.display_name if mentor_player else "their mentor"

                self._record_mentorship_memory(
                    scholar,
                    mentor_player,
                    event="progression",
                    track=track,
                    timestamp=now,
                )

                quote = f"Advanced to {scholar.career['tier']} under the guidance of {mentor_name}."
                press = academic_gossip(
                    GossipContext(scholar=scholar.name, quote=quote, trigger="Career advancement"),
                )
                releases.append(press)
                self._archive_press(press, now)
                layers = self._multi_press.generate_mentorship_layers(
                    mentor=mentor_name,
                    scholar=scholar,
                    phase="progression",
                    track=track,
                )
                releases.extend(
                    self._apply_multi_press_layers(
                        layers,
                        skip_types={press.type},
                        timestamp=now,
                        event_type="mentorship",
                    )
                )
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="career_progression",
                        payload={
                            "scholar": scholar.id,
                            "new_tier": scholar.career["tier"],
                            "mentor": mentorship[1],
                        },
                    )
                )

                # Complete mentorship after max tier reached
                if idx == len(ladder) - 2:  # Just reached final tier
                    self.state.complete_mentorship(mentorship[0], now)
                    self._record_mentorship_memory(
                        scholar,
                        mentor_player,
                        event="completion",
                        track=track,
                        timestamp=now,
                    )
                    complete_press = academic_gossip(
                        GossipContext(
                            scholar=mentor_name,
                            quote=f"My mentorship of {scholar.name} is complete. They have reached the pinnacle of their field.",
                            trigger="Mentorship completed",
                        )
                    )
                    releases.append(complete_press)
                    self._archive_press(complete_press, now)
                    completion_layers = self._multi_press.generate_mentorship_layers(
                        mentor=mentor_name,
                        scholar=scholar,
                        phase="completion",
                        track=track,
                    )
                    releases.extend(
                        self._apply_multi_press_layers(
                            completion_layers,
                            skip_types={complete_press.type},
                            timestamp=now,
                            event_type="mentorship",
                        )
                    )

            self.state.save_scholar(scholar)
        return releases

    def _resolve_mentorships(self) -> List[PressRelease]:
        """Resolve pending mentorships at digest time."""
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        due_orders = self.state.fetch_due_orders("mentorship_activation", now)
        for order in due_orders:
            order_id = order["id"]
            payload = order["payload"]
            mentorship_id = payload.get("mentorship_id")
            scholar_id = payload.get("scholar_id")
            career_track = payload.get("career_track")
            mentorship = (
                self.state.get_mentorship_by_id(mentorship_id)
                if mentorship_id is not None
                else None
            )
            if not mentorship:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "mentorship_missing"},
                )
                continue

            _, player_id, scholar_id_db, _, status = mentorship
            scholar_id = scholar_id or scholar_id_db
            scholar = self.state.get_scholar(scholar_id)
            player = self.state.get_player(player_id)
            if not scholar or not player or status != "pending":
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "mentorship_unavailable"},
                )
                continue

            existing = self.state.get_active_mentorship(scholar_id)
            if existing:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "duplicate_activation"},
                )
                continue

            self.state.activate_mentorship(mentorship_id)

            track_name = scholar.career.get("track", "Academia")
            if career_track and career_track in self._CAREER_TRACKS:
                if track_name != career_track:
                    scholar.career["track"] = career_track
                    scholar.career["tier"] = self._CAREER_TRACKS[career_track][0]
                    scholar.career["ticks"] = 0
                track_name = career_track

            self._record_mentorship_memory(
                scholar,
                player,
                event="activation",
                track=track_name,
                timestamp=now,
            )
            self.state.save_scholar(scholar)

            quote = f"The mentorship between {player.display_name} and {scholar.name} has officially commenced."
            press = academic_gossip(
                GossipContext(
                    scholar="The Academy",
                    quote=quote,
                    trigger="Mentorship activation",
                )
            )
            press = self._enhance_press_release(
                press,
                base_body=press.body,
                persona_name=player.display_name,
                persona_traits=None,
                extra_context={
                    "event": "mentorship_activated",
                    "mentor": player.display_name,
                    "scholar": scholar.name,
                    "career_track": track_name,
                },
            )
            releases.append(press)
            self._archive_press(press, now)

            self.state.append_event(
                Event(
                    timestamp=now,
                    action="mentorship_activated",
                    payload={
                        "player": player_id,
                        "scholar": scholar_id,
                        "mentorship_id": mentorship_id,
                    },
                )
            )
            self.state.update_order_status(
                order_id,
                "completed",
                result={"mentorship_id": mentorship_id},
            )

            layers = self._multi_press.generate_mentorship_layers(
                mentor=player.display_name,
                scholar=scholar,
                phase="activation",
                track=career_track or scholar.career.get("track", "Academia"),
            )
            self._apply_multi_press_layers(
                layers,
                skip_types={press.type},
                timestamp=now,
                event_type="mentorship",
            )

        return releases

    def _resolve_followups(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        for followup_id, scholar_id, kind, payload in self.state.due_followups(now):
            if kind == "symposium_reprimand":
                player_record = self.state.get_player(scholar_id)
                display_name = payload.get("display_name") or (
                    player_record.display_name if player_record else scholar_id
                )
                faction = payload.get("faction", "the Academy")
                penalty_influence = int(payload.get("penalty_influence", 0))
                penalty_reputation = int(payload.get("penalty_reputation", 0))
                reprisal_level = int(payload.get("reprisal_level", 1))
                remaining = int(payload.get("remaining", 0))
                headline = f"Symposium Reprimand: {display_name}".rstrip()
                impacts = []
                if penalty_influence:
                    impacts.append(f"{penalty_influence} influence seized by {faction}")
                if penalty_reputation:
                    impacts.append(f"{penalty_reputation} reputation deducted")
                impact_text = "; ".join(impacts) if impacts else "Public reprimand issued"
                body = (
                    f"{display_name} faces a symposium reprisal from {faction}. {impact_text}. "
                    f"Outstanding debt: {remaining}. Reprisal level now {reprisal_level}."
                )
                press = PressRelease(
                    type="symposium_reprimand",
                    headline=headline,
                    body=body,
                    metadata={
                        "player_id": payload.get("player_id") or scholar_id,
                        "faction": faction,
                        "reprisal_level": reprisal_level,
                        "remaining": remaining,
                        "penalty_influence": penalty_influence,
                        "penalty_reputation": penalty_reputation,
                    },
                )
                self._archive_press(press, now)
                releases.append(press)
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="symposium_reprimand",
                        payload={
                            "player": payload.get("player_id") or scholar_id,
                            "faction": faction,
                            "reprisal_level": reprisal_level,
                            "remaining": remaining,
                        },
                    )
                )
                self.state.clear_followup(
                    followup_id,
                    result={"resolution": "symposium_reprimand"},
                )
                continue

            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                self.state.clear_followup(
                    followup_id,
                    status="cancelled",
                    result={"reason": "scholar_missing"},
                )
                continue
            if kind in {"defection_grudge", "defection_return"}:
                scenario = payload.get("scenario")
                if kind == "defection_grudge":
                    scenario = scenario or "rivalry"
                else:
                    scenario = scenario or "reconciliation"

                former_employer_id = payload.get("former_employer") or scholar.contract.get("sidecast_sponsor") or scholar.contract.get("employer")
                former_employer = self.state.get_player(former_employer_id)
                former_name = former_employer.display_name if former_employer else (former_employer_id or "their patron")

                if scenario == "reconciliation":
                    scholar.memory.adjust_feeling(former_employer_id or "patron", 1.5)
                    # Return scholar to their prior patron if known
                    if former_employer_id:
                        scholar.contract["employer"] = former_employer_id
                else:
                    new_faction = payload.get("new_faction") or payload.get("faction") or scholar.contract.get("employer", "Unknown")
                    scholar.memory.adjust_feeling(new_faction, -1.5)

                new_faction_name = payload.get("new_faction") or payload.get("faction") or scholar.contract.get("employer", "Unknown")

                layers = self._multi_press.generate_defection_epilogue_layers(
                    scenario=scenario,
                    scholar_name=scholar.name,
                    former_faction=former_name,
                    new_faction=new_faction_name,
                    former_employer=former_name,
                )
                immediate_layers = self._apply_multi_press_layers(
                    layers,
                    skip_types=set(),
                    timestamp=now,
                    event_type="defection_epilogue",
                )
                releases.extend(immediate_layers)
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="defection_epilogue",
                        payload={
                            "scholar": scholar.id,
                            "scenario": scenario,
                            "former_faction": former_name,
                            "new_faction": new_faction_name,
                        },
                    )
                )
                self.state.save_scholar(scholar)
                self.state.clear_followup(
                    followup_id,
                    result={"resolution": f"defection_{scenario}"},
                )
                continue
            elif kind == "recruitment_grudge":
                scholar.memory.adjust_feeling(payload.get("player", "Unknown"), -1.0)
                quote = "The slighted scholar sharpens their public retort."
            elif kind.startswith("sidecast_"):
                arc_key = payload.get("arc") or scholar.contract.get("sidecast_arc") or self._multi_press.pick_sidecast_arc()
                phase = payload.get("phase") or kind.split("_", 1)[1]
                sponsor_id = payload.get("sponsor") or scholar.contract.get("sidecast_sponsor")
                sponsor_player = self.state.get_player(sponsor_id) if sponsor_id else None
                sponsor_display = sponsor_player.display_name if sponsor_player else (sponsor_id or "Patron")
                expedition_type = payload.get("expedition_type")
                expedition_code = payload.get("expedition_code")

                plan = self._multi_press.generate_sidecast_layers(
                    arc_key=arc_key,
                    phase=phase,
                    scholar=scholar,
                    sponsor=sponsor_display,
                    expedition_type=expedition_type,
                    expedition_code=expedition_code,
                )

                self._record_sidecast_memory(
                    scholar,
                    sponsor_id,
                    arc=arc_key,
                    phase=phase,
                    timestamp=now,
                    extra={
                        "expedition_code": expedition_code,
                        "expedition_type": expedition_type,
                    },
                )
                self.state.save_scholar(scholar)

                immediate_layers = self._apply_multi_press_layers(
                    plan.layers,
                    skip_types=set(),
                    timestamp=now,
                    event_type="sidecast",
                )
                releases.extend(immediate_layers)

                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="sidecast_followup",
                        payload={
                            "scholar": scholar.id,
                            "arc": arc_key,
                            "phase": phase,
                            "sponsor": sponsor_id,
                        },
                    )
                )

                self.state.clear_followup(
                    followup_id,
                    result={"resolution": f"sidecast_{phase}"},
                )

                if plan.next_phase:
                    next_delay = plan.next_delay_hours
                    if next_delay is None:
                        next_delay = self._multi_press.sidecast_phase_delay(arc_key, plan.next_phase, default_hours=36.0)
                    scheduled_at = now + timedelta(hours=next_delay)
                    self.state.enqueue_order(
                        f"followup:sidecast_{plan.next_phase}",
                        actor_id=scholar.id,
                        subject_id=sponsor_id,
                        payload={
                            "arc": arc_key,
                            "phase": plan.next_phase,
                            "sponsor": sponsor_id,
                            "expedition_code": expedition_code,
                            "expedition_type": expedition_type,
                        },
                        scheduled_at=scheduled_at,
                    )
                continue
            elif kind == "sideways_vignette":
                headline = payload.get("headline", f"Sideways Vignette — {scholar.name}")
                body = payload.get("body", "")
                tags = payload.get("tags", [])
                base_press = PressRelease(
                    type="sideways_vignette",
                    headline=headline,
                    body=body,
                    metadata={
                        "scholar": scholar.id,
                        "tags": tags,
                        "discovery": payload.get("discovery"),
                    },
                )
                self._archive_press(base_press, now)
                releases.append(base_press)

                gossip_entries = payload.get("gossip") or []
                for quote in gossip_entries:
                    ctx = GossipContext(
                        scholar=scholar.name,
                        quote=quote,
                        trigger="Sideways Discovery",
                    )
                    gossip_press = academic_gossip(ctx)
                    self._archive_press(gossip_press, now)
                    releases.append(gossip_press)
                self.state.append_event(
                    Event(
                        timestamp=now,
                        action="sideways_vignette",
                        payload={
                            "scholar": scholar.id,
                            "headline": headline,
                            "tags": tags,
                        },
                    )
                )
                self.state.clear_followup(
                    followup_id,
                    result={"resolution": "sideways_vignette"},
                )
                continue
            elif kind == "evaluate_offer":
                # Resolve offer negotiation
                offer_id = payload.get("offer_id")
                if offer_id:
                    negotiation_press = self.resolve_offer_negotiation(offer_id)
                    releases.extend(negotiation_press)
                    self.state.clear_followup(
                        followup_id,
                        result={"resolution": "offer_negotiation"},
                    )
                    continue  # Skip the normal gossip generation
                quote = "The negotiation deadline has arrived."
            elif kind == "evaluate_counter":
                # Resolve counter-offer negotiation
                counter_offer_id = payload.get("counter_offer_id")
                if counter_offer_id:
                    negotiation_press = self.resolve_offer_negotiation(counter_offer_id)
                    releases.extend(negotiation_press)
                    self.state.clear_followup(
                        followup_id,
                        result={"resolution": "counter_negotiation"},
                    )
                    continue  # Skip the normal gossip generation
                quote = "The counter-offer awaits final resolution."
            else:
                quote = "An unresolved thread lingers in the archives."
            press = academic_gossip(
                GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=kind.replace("_", " ").title(),
                )
            )
            self._archive_press(press, now)
            releases.append(press)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="followup_resolved",
                    payload={"scholar": scholar.id, "kind": kind, "order_id": followup_id},
                )
            )
            self.state.save_scholar(scholar)
            self.state.clear_followup(
                followup_id,
                result={"resolution": kind},
            )
        return releases

    def _schedule_symposium_reminders(
        self,
        *,
        topic_id: int,
        topic: str,
        start_time: datetime,
        pledge_base: int,
    ) -> None:
        players = list(self.state.all_players())
        if not players:
            return

        first_delay = max(self.settings.symposium_first_reminder_hours, 0.0)
        escalation_delay = max(self.settings.symposium_escalation_hours, 0.0)

        first_delta = timedelta(hours=first_delay)
        escalation_delta = timedelta(hours=escalation_delay)

        for player in players:
            pledge = self.state.get_symposium_pledge(topic_id=topic_id, player_id=player.id)
            pledged_amount = int(pledge.get("pledge_amount", pledge_base)) if pledge else pledge_base
            if first_delay >= 0:
                self.state.enqueue_order(
                    "symposium_vote_reminder",
                    actor_id=player.id,
                    subject_id=str(topic_id),
                    payload={
                        "topic_id": topic_id,
                        "player_id": player.id,
                        "topic": topic,
                        "reminder": "first",
                        "pledge_amount": pledged_amount,
                    },
                    scheduled_at=start_time + first_delta,
                )
            if escalation_delay > first_delay:
                self.state.enqueue_order(
                    "symposium_vote_reminder",
                    actor_id=player.id,
                    subject_id=str(topic_id),
                    payload={
                        "topic_id": topic_id,
                        "player_id": player.id,
                        "topic": topic,
                        "reminder": "escalation",
                        "pledge_amount": pledged_amount,
                    },
                    scheduled_at=start_time + escalation_delta,
                )

    def _process_symposium_reminders(self) -> List[PressRelease]:
        releases: List[PressRelease] = []
        now = datetime.now(timezone.utc)
        due_orders = self.state.fetch_due_orders("symposium_vote_reminder", now)
        for order in due_orders:
            order_id = order["id"]
            payload = order["payload"]
            topic_id = int(order.get("subject_id") or payload.get("topic_id"))
            player_id = order.get("actor_id") or payload.get("player_id")
            reminder_level = payload.get("reminder", "first")

            topic_meta = self.state.get_symposium_topic(topic_id)
            if not topic_meta or topic_meta.get("status") != "voting":
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "topic_closed"},
                )
                continue

            if not player_id:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "missing_player"},
                )
                continue

            if self.state.has_symposium_vote(topic_id, player_id):
                self.state.update_order_status(
                    order_id,
                    "completed",
                    result={"reason": "already_voted"},
                )
                continue

            player = self.state.get_player(player_id)
            if not player:
                self.state.update_order_status(
                    order_id,
                    "cancelled",
                    result={"reason": "player_missing"},
                )
                continue

            topic = payload.get("topic") or topic_meta.get("topic", "the symposium topic")
            pledged_amount = int(
                payload.get("pledge_amount", self.settings.symposium_pledge_base)
            )
            participation = self.state.get_symposium_participation(player_id)
            grace_limit = self.settings.symposium_grace_misses
            grace_used = int(participation.get("grace_miss_consumed", 0)) if participation else 0
            grace_remaining = max(0, grace_limit - grace_used)
            if reminder_level == "escalation":
                body = (
                    f"{player.display_name}, the Academy notes you have not yet cast a vote on "
                    f"'{topic}'. Missing this symposium will forfeit {pledged_amount} influence. "
                    "Use /symposium_vote before resolution to keep your pledge intact."
                )
            else:
                if grace_remaining > 0:
                    plural = "s" if grace_remaining != 1 else ""
                    grace_text = (
                        f"You have {grace_remaining} grace miss{plural} remaining; voting preserves it."
                    )
                else:
                    grace_text = (
                        f"You are out of grace—silence will cost {pledged_amount} influence."
                    )
                body = (
                    f"{player.display_name} is requested to cast a vote on '{topic}'. "
                    f"{grace_text} Use /symposium_vote to weigh in."
                )

            press = PressRelease(
                type="symposium_reminder",
                headline=f"Vote Required: {topic}",
                body=body,
                metadata={
                    "topic_id": topic_id,
                    "player_id": player_id,
                    "reminder_level": reminder_level,
                    "pledge_amount": pledged_amount,
                },
            )
            press = self._enhance_press_release(
                press,
                base_body=press.body,
                persona_name="The Academy",
                persona_traits=None,
                extra_context={
                    "event": "symposium_reminder",
                    "topic": topic,
                    "player": player.display_name,
                    "reminder_level": reminder_level,
                },
            )
            self._archive_press(press, now)
            releases.append(press)
            self.state.append_event(
                Event(
                    timestamp=now,
                    action="symposium_vote_reminder",
                    payload={
                        "topic_id": topic_id,
                        "player": player_id,
                        "reminder_level": reminder_level,
                        "pledge_amount": pledged_amount,
                    },
                )
            )
            self.state.update_order_status(
                order_id,
                "completed",
                result={"reminder": reminder_level},
            )
        return releases
    def _apply_reputation_change(
        self, player: Player, delta: int, confidence: ConfidenceLevel
    ) -> int:
        bounds = self.settings.reputation_bounds
        new_value = player.adjust_reputation(delta, bounds["min"], bounds["max"])
        if confidence is ConfidenceLevel.STAKE_CAREER:
            player.cooldowns["recruitment"] = max(2, player.cooldowns.get("recruitment", 0))
        return new_value

    def _apply_expedition_costs(self, player: Player, expedition_type: str, funding: List[str]) -> None:
        costs = self._EXPEDITION_COSTS.get(expedition_type, {})
        for faction, amount in costs.items():
            self._apply_influence_change(player, faction, -amount)
        for faction in funding:
            self._apply_influence_change(player, faction, 1)

    def _apply_expedition_rewards(
        self, player: Player, expedition_type: str, result
    ) -> None:
        if result.outcome == ExpeditionOutcome.FAILURE:
            return
        rewards = self._EXPEDITION_REWARDS.get(expedition_type, {})
        for faction, amount in rewards.items():
            self._apply_influence_change(player, faction, amount)

    def _update_relationships_from_result(self, order: ExpeditionOrder, result) -> None:
        outcome = result.outcome
        for scholar_id in order.team:
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue
            if outcome == ExpeditionOutcome.FAILURE:
                scholar.memory.adjust_feeling(order.player_id, -2.0)
            else:
                scholar.memory.adjust_feeling(order.player_id, 1.0)
            self.state.save_scholar(scholar)
            feeling = scholar.memory.feelings.get(order.player_id, 0.0)
            self.state.update_relationship(scholar_id, order.player_id, feeling)

    def _apply_sideways_effects(
        self, order: ExpeditionOrder, result, player: Player
    ) -> List[PressRelease]:
        """Apply mechanical effects from sideways discoveries."""
        if not result.sideways_effects:
            return []

        releases = []
        now = datetime.now(timezone.utc)
        followups_scheduled = False

        for effect in result.sideways_effects:
            tags = effect.payload.get("tags")
            followups = effect.payload.get("followups")
            if followups and not followups_scheduled:
                self._schedule_sideways_followups(
                    order=order,
                    followups=followups,
                    timestamp=now,
                    tags=tags,
                )
                followups_scheduled = True

            if effect.effect_type == SidewaysEffectType.FACTION_SHIFT:
                # Apply faction influence change
                faction = effect.payload["faction"]
                amount = effect.payload["amount"]
                old_influence = player.influence.get(faction, 0)
                self._apply_influence_change(player, faction, amount)
                releases.append(
                    PressRelease(
                        type="faction_shift",
                        headline=f"Expedition Discovery Shifts {faction} Relations",
                        body=f"{effect.description}. {player.display_name}'s {faction} influence changes by {amount} (from {old_influence} to {player.influence[faction]}).",
                        metadata={"player": player.display_name, "faction": faction, "change": amount},
                    )
                )
                self._attach_tags_to_release(releases[-1], tags)

            elif effect.effect_type == SidewaysEffectType.SPAWN_THEORY:
                # Create a new theory from the discovery
                theory_text = effect.payload["theory"]
                confidence = ConfidenceLevel(effect.payload["confidence"])
                deadline = (now + timedelta(days=7)).strftime("%Y-%m-%d")  # 7 days to support/challenge
                theory_record = TheoryRecord(
                    player_id=order.player_id,
                    theory=theory_text,
                    confidence=confidence.value,
                    timestamp=now,
                    supporters=[],  # Empty initially
                    deadline=deadline
                )
                self.state.record_theory(theory_record)
                releases.append(
                    PressRelease(
                        type="discovery_theory",
                        headline="Discovery Spawns New Theory",
                        body=f"{effect.description}. {player.display_name} proposes: '{theory_text}' with {confidence.value} confidence.",
                        metadata={"player": player.display_name, "theory": theory_text},
                    )
                )
                self._attach_tags_to_release(releases[-1], tags)

            elif effect.effect_type == SidewaysEffectType.CREATE_GRUDGE:
                # Create a grudge between scholars
                target_id = effect.payload["target"]
                intensity = effect.payload["intensity"]

                # If target is "random", pick a random scholar
                if target_id == "random":
                    scholars = list(self.state.all_scholars())
                    # Filter out scholars on the same team as the expedition
                    eligible = [s for s in scholars if s.id not in order.team]
                    if eligible:
                        target = self._rng.choice(eligible)
                        target_id = target.id
                        # Make the target scholar dislike the player
                        target.memory.adjust_feeling(order.player_id, -intensity)
                        self.state.save_scholar(target)
                        releases.append(
                            PressRelease(
                                type="scholar_grudge",
                                headline=f"{target.name} Objects to Expedition Approach",
                                body=f"{effect.description}. {target.name} expresses concerns about {player.display_name}'s expedition methods.",
                                metadata={"scholar": target.name, "player": player.display_name},
                            )
                        )
                        self._attach_tags_to_release(releases[-1], tags)

            elif effect.effect_type == SidewaysEffectType.QUEUE_ORDER:
                # Queue a follow-up order (conference, summit, etc.)
                order_type = effect.payload["order_type"]
                order_data = effect.payload["order_data"]

                if order_type == "conference":
                    # Auto-schedule a conference by first creating a theory
                    theory_text = order_data.get("topic", "Emergency colloquium on expedition findings")
                    # Submit the theory first
                    theory_record = TheoryRecord(
                        player_id=order.player_id,
                        theory=theory_text,
                        confidence=ConfidenceLevel.SUSPECT.value,
                        timestamp=now,
                        supporters=[],  # Empty initially
                        deadline=(now + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M")  # 48 hours for the conference
                    )
                    self.state.record_theory(theory_record)
                    # Get the theory ID we just created
                    theory_id = self.state.get_last_theory_id_by_player(order.player_id)
                    # Now launch a conference on this theory
                    if theory_id:
                        # Pick some random scholars as supporters/opposition
                        scholars = list(self.state.all_scholars())[:6]
                        supporters = [s.id for s in scholars[:3]]
                        opposition = [s.id for s in scholars[3:6]]
                        self.launch_conference(
                            order.player_id,
                            theory_id,
                            ConfidenceLevel.SUSPECT,
                            supporters,
                            opposition
                        )
                        releases.append(
                            PressRelease(
                                type="conference_scheduled",
                                headline="Emergency Colloquium Scheduled",
                                body=f"{effect.description}. Conference scheduled to discuss expedition findings.",
                                metadata={"player": player.display_name},
                            )
                        )
                        self._attach_tags_to_release(releases[-1], tags)

            elif effect.effect_type == SidewaysEffectType.REPUTATION_CHANGE:
                # Change player reputation
                amount = effect.payload["amount"]
                old_rep = player.reputation
                player.reputation = max(
                    self.settings.reputation_bounds["min"],
                    min(self.settings.reputation_bounds["max"], player.reputation + amount),
                )
                releases.append(
                    PressRelease(
                        type="reputation_shift",
                        headline="Discovery Affects Academic Standing",
                        body=f"{effect.description}. {player.display_name}'s reputation changes by {amount} (from {old_rep} to {player.reputation}).",
                        metadata={"player": player.display_name, "change": amount},
                    )
                )
                self._attach_tags_to_release(releases[-1], tags)

            elif effect.effect_type == SidewaysEffectType.UNLOCK_OPPORTUNITY:
                # Store opportunity in followups table for later resolution
                opportunity_type = effect.payload["type"]
                details = effect.payload["details"]
                deadline = now + timedelta(days=details.get("expires_in_days", 3))

                # Schedule the opportunity as a followup
                scholar_id = random.choice(order.team) if order.team else "unknown"
                self.state.schedule_followup(
                    scholar_id=scholar_id,
                    kind=opportunity_type,
                    resolve_at=deadline,
                    payload={
                        "source_type": "expedition_opportunity",
                        "source_id": order.code,
                        "details": details,
                    }
                )
                releases.append(
                    PressRelease(
                        type="opportunity_unlocked",
                        headline="New Opportunity Emerges",
                        body=f"{effect.description}. Opportunity expires in {details.get('expires_in_days', 3)} days.",
                        metadata={"player": player.display_name, "opportunity": opportunity_type},
                    )
                )
                self._attach_tags_to_release(releases[-1], tags)

        # Save player changes and archive press releases
        self.state.upsert_player(player)
        for release in releases:
            self._archive_press(release, now)

        releases.extend(self.release_scheduled_press(now))
        return releases

    @staticmethod
    def _attach_tags_to_release(release: PressRelease, tags: Optional[List[str]]) -> None:
        if not tags:
            return
        existing = release.metadata.setdefault("tags", [])
        for tag in tags:
            if tag not in existing:
                existing.append(tag)

    def _schedule_sideways_followups(
        self,
        *,
        order: ExpeditionOrder,
        followups: Dict[str, object],
        timestamp: datetime,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Schedule additional press or orders defined by sideways data."""

        press_entries = followups.get("press") if isinstance(followups, dict) else []
        if isinstance(press_entries, dict):
            press_entries = [press_entries]
        for entry in press_entries or []:
            if not isinstance(entry, dict):
                continue
            delay = int(entry.get("delay_minutes", 180))
            release_at = timestamp + timedelta(minutes=delay)
            headline = entry.get("headline") or f"Follow-up: Expedition {order.code}"
            body = entry.get("body") or ""
            release_type = entry.get("type", "sideways_followup")
            metadata = {
                "source": "sideways_followup",
                "order_code": order.code,
                "expedition_type": order.expedition_type,
            }
            if tags:
                metadata["tags"] = list(tags)
            self.state.enqueue_press_release(
                PressRelease(
                    type=release_type,
                    headline=headline,
                    body=body,
                    metadata=metadata,
                ),
                release_at,
            )
            self.state.append_event(
                Event(
                    timestamp=timestamp,
                    action="sideways_press_scheduled",
                    payload={
                        "order_code": order.code,
                        "headline": headline,
                        "delay_minutes": delay,
                        "type": release_type,
                    },
                )
            )

        order_entries = followups.get("orders") if isinstance(followups, dict) else []
        if isinstance(order_entries, dict):
            order_entries = [order_entries]
        for entry in order_entries or []:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("type")
            if not kind:
                continue
            delay = int(entry.get("delay_minutes", 0))
            scheduled_at = timestamp + timedelta(minutes=delay) if delay else None
            payload = entry.get("payload", {})
            payload = dict(payload) if isinstance(payload, dict) else {}
            payload.setdefault("source", "sideways_followup")
            payload.setdefault("order_code", order.code)
            if tags and "tags" not in payload:
                payload["tags"] = list(tags)
            self.state.enqueue_order(
                kind,
                actor_id=order.player_id,
                subject_id=order.code,
                payload=payload,
                scheduled_at=scheduled_at,
            )
            self.state.append_event(
                Event(
                    timestamp=timestamp,
                    action="sideways_order_scheduled",
                    payload={
                        "order_code": order.code,
                        "order_type": kind,
                        "delay_minutes": delay,
                    },
                )
            )

    def _apply_multi_press_layers(
        self,
        layers,
        *,
        skip_types: set[str],
        timestamp: datetime,
        event_type: str = "general",
    ) -> List[PressRelease]:
        """Render additional press layers, archiving each generated release."""

        if not layers:
            return []
        remaining = [layer for layer in layers if layer.type not in skip_types]
        if not remaining:
            return []
        telemetry = self._telemetry
        immediate: List[PressRelease] = []
        for layer in remaining:
            persona_hint: Optional[str] = None
            if hasattr(layer.context, "scholar"):
                persona_hint = getattr(layer.context, "scholar")
            elif isinstance(layer.context, dict):
                persona_hint = layer.context.get("persona")
            if telemetry is not None:
                telemetry.track_press_layer(
                    layer_type=layer.type,
                    event_type=event_type,
                    delay_minutes=float(layer.delay_minutes),
                    persona=persona_hint,
                )
            release = layer.generator(layer.context)
            if layer.tone_seed:
                release.metadata.setdefault("tone_seed", {})
                release.metadata["tone_seed"].update(layer.tone_seed)
            extra_context: Dict[str, object] = {
                "event_type": event_type,
                "layer_type": layer.type,
                "delay_minutes": layer.delay_minutes,
            }
            if layer.tone_seed:
                extra_context["tone_seed"] = layer.tone_seed
            base_body = release.body
            persona_traits = None
            if persona_hint:
                persona_traits = self._resolve_scholar_traits(persona_hint)
            release = self._enhance_press_release(
                release,
                base_body=base_body,
                persona_name=persona_hint,
                persona_traits=persona_traits,
                extra_context=extra_context,
            )
            if layer.delay_minutes <= 0:
                self._archive_press(release, timestamp)
                immediate.append(release)
                continue

            release.metadata.setdefault("scheduled", {})
            release.metadata["scheduled"].update(
                {
                    "delay_minutes": layer.delay_minutes,
                    "generated_at": timestamp.isoformat(),
                    "layer_type": layer.type,
                    "event_type": event_type,
                }
            )
            release_at = timestamp + timedelta(minutes=layer.delay_minutes)
            self.state.enqueue_press_release(release, release_at)
            self.state.append_event(
                Event(
                    timestamp=timestamp,
                    action="press_scheduled",
                    payload={
                        "headline": release.headline,
                        "release_at": release_at.isoformat(),
                        "layer_type": layer.type,
                    },
                )
            )
            self._queue_admin_notification(
                f"📰 Scheduled follow-up press '{release.headline}' for {release_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
        return immediate

    def _maybe_spawn_sidecast(self, order: ExpeditionOrder, result) -> Optional[PressRelease]:
        if result.outcome == ExpeditionOutcome.FAILURE:
            return None
        if sum(1 for _ in self.state.all_scholars()) >= self._MAX_SCHOLAR_ROSTER:
            return None
        identifier = f"s.proc-{self._generated_counter:03d}"
        self._generated_counter += 1
        scholar = self.repository.generate(self._rng, identifier)
        scholar.contract["employer"] = order.player_id
        arc_key = self._multi_press.pick_sidecast_arc()
        scholar.contract["sidecast_arc"] = arc_key
        scholar.contract["sidecast_sponsor"] = order.player_id
        now = datetime.now(timezone.utc)
        self._record_sidecast_memory(
            scholar,
            order.player_id,
            arc=arc_key,
            phase="spawn",
            timestamp=now,
            extra={
                "expedition": order.code,
                "expedition_type": order.expedition_type,
            },
        )
        self._append_contract_history(
            scholar,
            "expedition_links",
            {
                "expedition": order.code,
                "timestamp": now.isoformat(),
            },
        )
        self.state.save_scholar(scholar)
        ctx = GossipContext(
            scholar=scholar.name,
            quote="I saw the expedition and could not resist joining.",
            trigger=f"Expedition {order.code}",
        )
        press = academic_gossip(ctx)
        self.state.append_event(
            Event(
                timestamp=now,
                action="scholar_sidecast",
                payload={"scholar": scholar.id, "expedition": order.code},
            )
        )
        # Schedule debut follow-up to introduce the sidecast arc
        delay_hours = self._multi_press.sidecast_phase_delay(arc_key, "debut", default_hours=6.0)
        scheduled_at = now + timedelta(hours=delay_hours)
        self.state.enqueue_order(
            "followup:sidecast_debut",
            actor_id=scholar.id,
            subject_id=order.player_id,
            payload={
                "arc": arc_key,
                "phase": "debut",
                "sponsor": order.player_id,
                "expedition_code": order.code,
                "expedition_type": order.expedition_type,
            },
            scheduled_at=scheduled_at,
        )
        return press

    def _append_contract_history(
        self,
        scholar: Scholar,
        key: str,
        entry: Dict[str, object],
    ) -> None:
        history = scholar.contract.get(key)
        if not isinstance(history, list):
            history = []
            scholar.contract[key] = history
        history.append(entry)

    def _clamp_probability(self, value: float) -> float:
        return max(0.05, min(0.95, value))

    def _relationship_bonus(
        self,
        scholar: Scholar,
        player_id: str,
    ) -> Dict[str, object]:
        feeling = scholar.memory.feelings.get(player_id, 0.0)
        base_bonus = max(-0.2, min(0.2, feeling * 0.02))

        mentorship_bonus = 0.0
        active = self.state.get_active_mentorship(scholar.id)
        active_for_player = bool(active and active[1] == player_id)
        if active_for_player:
            mentorship_bonus += 0.05
        else:
            history = scholar.contract.get("mentorship_history")
            if isinstance(history, list):
                entries = [entry for entry in history if entry.get("mentor_id") == player_id]
                if entries:
                    last_event = entries[-1].get("event")
                    if last_event == "completion":
                        mentorship_bonus += 0.04
                    else:
                        mentorship_bonus += 0.02

        sidecast_bonus = 0.0
        sidecasts = scholar.contract.get("sidecast_history")
        if isinstance(sidecasts, list):
            if any(entry.get("sponsor_id") == player_id for entry in sidecasts):
                sidecast_bonus += 0.02

        total = base_bonus + mentorship_bonus + sidecast_bonus
        total = max(-0.25, min(0.25, total))

        return {
            "total": total,
            "feeling": feeling,
            "base_bonus": base_bonus,
            "mentorship_bonus": mentorship_bonus,
            "sidecast_bonus": sidecast_bonus,
            "active_mentorship": active_for_player,
        }

    def _player_faction_relationship(
        self,
        player: Player,
        faction: str,
        *,
        weight: Optional[float] = None,
    ) -> float:
        factor = weight if weight is not None else self.settings.seasonal_commitment_relationship_weight
        total = 0.0
        count = 0
        for scholar in self.state.all_scholars():
            if scholar.contract.get("employer") != player.id:
                continue
            if faction and scholar.contract.get("faction") != faction:
                continue
            feeling = scholar.memory.feelings.get(player.id, 0.0)
            total += feeling
            count += 1
            history = scholar.contract.get("mentorship_history")
            if isinstance(history, list):
                for entry in history:
                    if entry.get("mentor_id") == player.id:
                        total += 1.0
            sidecasts = scholar.contract.get("sidecast_history")
            if isinstance(sidecasts, list):
                if any(entry.get("sponsor_id") == player.id for entry in sidecasts):
                    total += 1.0
        if count == 0:
            influence = max(0.0, player.influence.get(faction, 0))
            if influence <= 0:
                return 0.0
            return max(-0.1, min(0.1, (influence / 10.0) * factor))
        average = total / count
        modifier = average * factor
        return max(-0.25, min(0.25, modifier))

    def _player_relationship_summary(self, player: Player, limit: int = 5) -> List[Dict[str, object]]:
        entries: List[Dict[str, object]] = []
        for scholar in self.state.all_scholars():
            feeling = scholar.memory.feelings.get(player.id)
            mentorship_history = scholar.contract.get("mentorship_history")
            mentorship_entries = []
            if isinstance(mentorship_history, list):
                mentorship_entries = [entry for entry in mentorship_history if entry.get("mentor_id") == player.id]

            sidecast_history = scholar.contract.get("sidecast_history")
            sidecast_entries = []
            if isinstance(sidecast_history, list):
                sidecast_entries = [entry for entry in sidecast_history if entry.get("sponsor_id") == player.id]

            if feeling is None and not mentorship_entries and not sidecast_entries:
                continue

            active = self.state.get_active_mentorship(scholar.id)
            active_for_player = bool(active and active[1] == player.id)

            last_mentorship_event = None
            last_mentorship_at = None
            if mentorship_entries:
                last_entry = mentorship_entries[-1]
                last_mentorship_event = last_entry.get("event")
                last_mentorship_at = last_entry.get("timestamp") or last_entry.get("resolved_at")

            last_sidecast_phase = None
            last_sidecast_at = None
            if sidecast_entries:
                last_sidecast = sidecast_entries[-1]
                last_sidecast_phase = last_sidecast.get("phase")
                last_sidecast_at = last_sidecast.get("timestamp")

            sidecast_arc = None
            if sidecast_entries:
                sidecast_arc = sidecast_entries[-1].get("arc") or scholar.contract.get("sidecast_arc")

            entries.append(
                {
                    "scholar": scholar.name,
                    "scholar_id": scholar.id,
                    "feeling": feeling or 0.0,
                    "active_mentorship": active_for_player,
                    "track": scholar.career.get("track"),
                    "tier": scholar.career.get("tier"),
                    "last_mentorship_event": last_mentorship_event,
                    "last_mentorship_at": last_mentorship_at,
                    "sidecast_arc": sidecast_arc,
                    "last_sidecast_phase": last_sidecast_phase,
                    "last_sidecast_at": last_sidecast_at,
                }
            )

        entries.sort(key=lambda item: item["feeling"], reverse=True)
        if limit > 0:
            entries = entries[:limit]
        return entries

    def _player_commitment_summary(self, player: Player, limit: int = 10) -> List[Dict[str, object]]:
        commitments = self.state.list_player_commitments(player.id)
        summary: List[Dict[str, object]] = []
        for entry in commitments:
            relationship = self._player_faction_relationship(
                player,
                entry.get("faction", ""),
            )
            summary.append(
                {
                    "id": entry.get("id"),
                    "faction": entry.get("faction"),
                    "tier": entry.get("tier"),
                    "base_cost": entry.get("base_cost"),
                    "start_at": entry.get("start_at"),
                    "end_at": entry.get("end_at"),
                    "status": entry.get("status"),
                    "relationship_modifier": relationship,
                    "last_processed_at": entry.get("last_processed_at"),
                }
            )
        summary.sort(key=lambda item: item.get("end_at") or datetime.max)
        if limit > 0:
            summary = summary[:limit]
        return summary

    def _player_investment_summary(self, player: Player) -> List[Dict[str, object]]:
        records = self.state.list_faction_investments(player.id)
        summary: Dict[str, Dict[str, object]] = {}
        for record in records:
            faction = record.get("faction") or "unaligned"
            entry = summary.setdefault(
                faction,
                {
                    "faction": faction,
                    "total": 0,
                    "count": 0,
                    "latest": None,
                    "programs": set(),
                },
            )
            entry["total"] += int(record.get("amount", 0))
            entry["count"] += 1
            created_at = record.get("created_at")
            if created_at and (
                entry["latest"] is None or created_at > entry["latest"]
            ):
                entry["latest"] = created_at
            program = record.get("program")
            if program:
                entry["programs"].add(program)
        output: List[Dict[str, object]] = []
        for faction, data in summary.items():
            output.append(
                {
                    "faction": faction,
                    "total": data["total"],
                    "count": data["count"],
                    "latest": data["latest"].isoformat() if isinstance(data["latest"], datetime) else None,
                    "programs": sorted(data["programs"]),
                }
            )
        output.sort(key=lambda item: item["total"], reverse=True)
        return output

    def _player_endowment_summary(self, player: Player) -> List[Dict[str, object]]:
        records = self.state.list_archive_endowments(player.id)
        summary: Dict[str, Dict[str, object]] = {}
        for record in records:
            faction = record.get("faction") or "unaligned"
            entry = summary.setdefault(
                faction,
                {
                    "faction": faction,
                    "total": 0,
                    "count": 0,
                    "latest": None,
                    "programs": set(),
                },
            )
            entry["total"] += int(record.get("amount", 0))
            entry["count"] += 1
            created_at = record.get("created_at")
            if created_at and (
                entry["latest"] is None or created_at > entry["latest"]
            ):
                entry["latest"] = created_at
            program = record.get("program")
            if program:
                entry["programs"].add(program)
        output: List[Dict[str, object]] = []
        for faction, data in summary.items():
            output.append(
                {
                    "faction": faction,
                    "total": data["total"],
                    "count": data["count"],
                    "latest": data["latest"].isoformat() if isinstance(data["latest"], datetime) else None,
                    "programs": sorted(data["programs"]),
                }
            )
        output.sort(key=lambda item: item["total"], reverse=True)
        return output

    def _advance_faction_projects(self, now: datetime) -> List[PressRelease]:
        releases: List[PressRelease] = []
        projects = self.state.list_active_faction_projects()
        if not projects:
            return releases

        players = list(self.state.all_players())
        for project in projects:
            faction = project.get("faction", "")
            base_increment = self.settings.faction_project_base_progress_weight
            total_progress = project.get("progress", 0.0)
            contributions: List[Dict[str, object]] = []

            for player in players:
                influence = max(0.0, player.influence.get(faction, 0))
                relationship = self._player_faction_relationship(
                    player,
                    faction,
                    weight=self.settings.faction_project_relationship_weight,
                )
                contribution = influence * base_increment + relationship
                if contribution <= 0:
                    continue
                total_progress += contribution
                contributions.append(
                    {
                        "player": player.display_name,
                        "contribution": contribution,
                        "relationship_modifier": relationship,
                        "influence": influence,
                    }
                )

            if not contributions:
                continue

            self.state.update_faction_project_progress(project["id"], total_progress, now)

            ctx = FactionProjectUpdateContext(
                name=project.get("name", "Project"),
                faction=faction or "Unaligned",
                progress=total_progress,
                target=project.get("target_progress", 0.0),
                contributions=contributions,
            )
            release = faction_project_update(ctx)
            release.metadata.setdefault("project", {}).update(
                {
                    "id": project.get("id"),
                    "progress": total_progress,
                    "target": project.get("target_progress", 0.0),
                }
            )
            self._archive_press(release, now)
            releases.append(release)

            if total_progress >= project.get("target_progress", 0.0):
                self.state.complete_faction_project(project["id"], now)
                completion_release = faction_project_complete(
                    FactionProjectUpdateContext(
                        name=project.get("name", "Project"),
                        faction=faction or "Unaligned",
                        progress=total_progress,
                        target=project.get("target_progress", 0.0),
                        contributions=contributions,
                    )
                )
                completion_release.metadata.setdefault("project", {}).update(
                    {
                        "id": project.get("id"),
                        "completed_at": now.isoformat(),
                    }
                )
                self._archive_press(completion_release, now)
                releases.append(completion_release)

                reward = self.settings.faction_project_completion_reward
                if reward > 0:
                    for entry in contributions:
                        player = next(
                            (p for p in players if p.display_name == entry["player"]),
                            None,
                        )
                        if not player:
                            continue
                        self._apply_influence_change(player, faction, reward)
                        self.state.upsert_player(player)

            try:
                self._telemetry.track_game_progression(
                    "faction_project_progress",
                    float(total_progress),
                    details={
                        "project_id": project.get("id"),
                        "faction": faction,
                    },
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to record faction project telemetry", exc_info=True)

        return releases

    def _record_mentorship_memory(
        self,
        scholar: Scholar,
        mentor: Optional[Player],
        *,
        event: str,
        track: str,
        timestamp: datetime,
    ) -> None:
        if mentor is None:
            return
        mentor_id = mentor.id
        delta_map = {
            "activation": 1.0,
            "progression": 0.5,
            "completion": 1.5,
        }
        delta = delta_map.get(event, 0.0)
        if delta:
            scholar.memory.adjust_feeling(mentor_id, delta)

        details = {
            "event": event,
            "mentor": mentor.display_name,
            "mentor_id": mentor_id,
            "track": track,
        }
        scholar.memory.record_fact(
            MemoryFact(
                timestamp=timestamp,
                type="mentorship",
                subject=mentor_id,
                details=details,
            )
        )

        self._append_contract_history(
            scholar,
            "mentorship_history",
            {
                "event": event,
                "mentor_id": mentor_id,
                "mentor": mentor.display_name,
                "track": track,
                "timestamp": timestamp.isoformat(),
            },
        )

    def _record_sidecast_memory(
        self,
        scholar: Scholar,
        sponsor_id: Optional[str],
        *,
        arc: str,
        phase: str,
        timestamp: datetime,
        extra: Optional[Dict[str, object]] = None,
    ) -> None:
        delta_map = {
            "spawn": 0.75,
            "debut": 1.0,
            "integration": 0.6,
            "spotlight": 1.2,
        }
        if sponsor_id:
            delta = delta_map.get(phase, 0.4)
            if delta:
                scholar.memory.adjust_feeling(sponsor_id, delta)
        subject = sponsor_id or arc
        details = {
            "arc": arc,
            "phase": phase,
            "sponsor_id": sponsor_id,
        }
        if extra:
            details.update(extra)
        scholar.memory.record_fact(
            MemoryFact(
                timestamp=timestamp,
                type="sidecast",
                subject=subject,
                details=details,
            )
        )
        self._append_contract_history(
            scholar,
            "sidecast_history",
            {
                "arc": arc,
                "phase": phase,
                "sponsor_id": sponsor_id,
                "timestamp": timestamp.isoformat(),
                "details": details,
            },
        )

    def _generate_reactions(self, team: List[str], result) -> List[str]:
        reactions = []
        for scholar_id in team:
            scholar = self.state.get_scholar(scholar_id)
            if not scholar:
                continue
            tone = "thrilled" if result.outcome in {ExpeditionOutcome.SUCCESS, ExpeditionOutcome.LANDMARK} else "wary"
            phrase = scholar.catchphrase.format(
                evidence="evidence",
                topic="the work",
                concept="collaboration",
                reckless_method="dynamite",
                premise="the data holds",
                wild_leap="we can fly",
            )
            reactions.append(f"{scholar.name} ({tone}): {phrase}")
        return reactions

    def _ensure_influence_structure(self, player: Player) -> None:
        for faction in self._FACTIONS:
            player.influence.setdefault(faction, 0)
        if player.cooldowns is None:
            player.cooldowns = {}

    def _apply_influence_change(self, player: Player, faction: str, delta: int) -> int:
        self._ensure_influence_structure(player)
        current = player.influence.get(faction, 0)
        cap = self._influence_cap(player)
        new_value = current + delta
        if delta > 0:
            new_value = min(cap, new_value)
        player.influence[faction] = new_value
        return new_value

    def _influence_cap(self, player: Player) -> int:
        base = int(self.settings.influence_caps.get("base", 5))
        per_rep = float(self.settings.influence_caps.get("per_reputation", 0.0))
        dynamic = base + int(per_rep * max(0, player.reputation))
        return max(base, dynamic)

    def _require_reputation(self, player: Player, action: str) -> None:
        threshold = self.settings.action_thresholds.get(action)
        if threshold is None:
            return
        if player.reputation < threshold:
            raise PermissionError(
                f"Action '{action}' requires reputation {threshold} but {player.display_name} has {player.reputation}."
            )

__all__ = ["GameService", "ExpeditionOrder"]
