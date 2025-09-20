"""Scheduler utilities for Gazette ticks."""
from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .models import PressRelease
from .service import GameService
from .telemetry import get_telemetry

logger = logging.getLogger(__name__)


class GazetteScheduler:
    """Schedules Gazette digests and weekly symposium events."""

    def __init__(
        self,
        service: GameService,
        publisher: Optional[Callable[[PressRelease], None]] = None,
        admin_publisher: Optional[Callable[[str], None]] = None,
        admin_file_publisher: Optional[Callable[[Path, str], None]] = None,
        upcoming_publisher: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.service = service
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()
        self._publisher = publisher
        self._admin_publisher = admin_publisher
        self._admin_file_publisher = admin_file_publisher
        self._upcoming_publisher = upcoming_publisher
        self._alert_digest_ms = float(os.getenv("GREAT_WORK_ALERT_MAX_DIGEST_MS", "5000")) or 0.0
        self._alert_queue_size = int(os.getenv("GREAT_WORK_ALERT_MAX_QUEUE", "12")) or 0
        self._alert_release_min = int(os.getenv("GREAT_WORK_ALERT_MIN_RELEASES", "1")) or 0
        publish_dir = os.getenv("GREAT_WORK_ARCHIVE_PUBLISH_DIR", "web_archive_public")
        self._archive_publish_dir = (
            Path(publish_dir).resolve() if publish_dir else None
        )
        self._archive_snapshot_limit = int(os.getenv("GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS", "30") or 0)

    def start(self) -> None:
        for digest_time in self.settings.gazette_times:
            hour, minute = map(int, digest_time.split(":"))
            self.scheduler.add_job(self._publish_digest, "cron", hour=hour, minute=minute)
        self.scheduler.add_job(self._host_symposium, "cron", day_of_week=self.settings.symposium_day.lower(), hour=12)
        self.scheduler.start()
        logger.info("GazetteScheduler started with digests at %s", self.settings.gazette_times)

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    def _publish_digest(self) -> None:
        start = time.perf_counter()
        current_time = datetime.now(timezone.utc)
        if self.service.is_paused():
            message = self.service.pause_reason() or "Game is paused"
            self._notify_admin(f"⏸️ Digest skipped — {message}")
            self._emit_admin_notifications()
            return
        digest_releases = self.service.advance_digest()
        releases = digest_releases + self.service.resolve_pending_expeditions()
        for press in releases:
            self._emit_release(press)

        highlight_press = self.service.create_digest_highlights(now=current_time)
        if highlight_press is not None:
            self._emit_release(highlight_press)
            releases.append(highlight_press)

        release_count = len(releases)
        if release_count == 0:
            logger.info("No expeditions to report this digest")
            self._emit_admin_notifications()
            duration_ms = (time.perf_counter() - start) * 1000
            telemetry = get_telemetry()
            try:
                telemetry.track_digest(
                    duration_ms=duration_ms,
                    release_count=0,
                    scheduled_queue_size=self.service.pending_press_count(),
                )
            except Exception:  # pragma: no cover
                logger.exception("Failed to record digest telemetry")
            self._evaluate_alerts(duration_ms=duration_ms, release_count=0)
            self._emit_upcoming_highlights()
            return
        
        # Export web archive after digest
        try:
            archive_path = self.service.export_web_archive(Path("web_archive"), source="scheduler")
            logger.info(f"Web archive exported to {archive_path}")
            self._publish_to_container(archive_path)
            if self._admin_file_publisher is not None:
                snapshot_path = self._package_archive(archive_path)
                caption = f"📚 Web archive snapshot ready ({snapshot_path.name})"
                self._admin_file_publisher(snapshot_path, caption)
                logger.info("Web archive snapshot published to admin channel: %s", snapshot_path)
        except Exception:
            logger.exception("Failed to export web archive during digest")
        self._emit_admin_notifications()

        duration_ms = (time.perf_counter() - start) * 1000
        telemetry = get_telemetry()
        try:
            telemetry.track_digest(
                duration_ms=duration_ms,
                release_count=release_count,
                scheduled_queue_size=self.service.pending_press_count(),
            )
        except Exception:  # pragma: no cover - defensive logging only
            logger.exception("Failed to record digest telemetry")

        self._evaluate_alerts(
            duration_ms=duration_ms,
            release_count=release_count,
        )
        self._emit_upcoming_highlights()

    def _host_symposium(self) -> None:
        """Host weekly symposium with randomly selected topic."""
        try:
            press = self.service.start_symposium()
        except Exception:
            logger.exception("Failed to start symposium")
            return

        self._emit_release(press)
        self._emit_admin_notifications()

    def _emit_release(self, press: PressRelease) -> None:
        if self._publisher is not None:
            try:
                self._publisher(press)
                return
            except Exception:  # pragma: no cover - defensive logging only
                logger.exception("Failed to publish Gazette item")
        logger.info("%s\n%s", press.headline, press.body)

    def _notify_admin(self, message: str) -> None:
        if self._admin_publisher is not None:
            try:
                self._admin_publisher(message)
                return
            except Exception:
                logger.exception("Failed to send admin notification")
        logger.info("ADMIN: %s", message)

    def _emit_admin_notifications(self) -> None:
        for message in self.service.drain_admin_notifications():
            self._notify_admin(message)

    def _package_archive(self, archive_dir: Path) -> Path:
        """Create a timestamped ZIP snapshot of the archive directory."""

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        snapshots_dir = archive_dir.parent / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        base_name = snapshots_dir / f"web_archive_{timestamp}"
        zip_file = shutil.make_archive(str(base_name), "zip", root_dir=archive_dir)
        snapshot_path = Path(zip_file)
        if self._archive_snapshot_limit > 0:
            self._prune_snapshots(snapshots_dir)
        return snapshot_path

    def _publish_to_container(self, archive_path: Path) -> None:
        """Sync the exported archive into the container-served directory."""

        if self._archive_publish_dir is None:
            return
        try:
            source = archive_path.resolve()
            target = self._archive_publish_dir
            if source == target:
                logger.debug("Archive publish target matches export directory; skipping sync")
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
            get_telemetry().track_system_event(
                "archive_published_container",
                source="gazette_scheduler",
            )
            logger.info("Archive published to container directory: %s", target)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Failed to publish archive to container directory")
            self._notify_admin(
                f"⚠️ Failed to publish archive to container directory: {exc}"
            )
            get_telemetry().track_system_event(
                "archive_publish_failed",
                source="gazette_scheduler",
                reason=str(exc),
            )

    def _prune_snapshots(self, snapshots_dir: Path) -> None:
        """Enforce snapshot retention limits."""

        if self._archive_snapshot_limit <= 0:
            return
        snapshots = sorted(
            snapshots_dir.glob("web_archive_*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in snapshots[self._archive_snapshot_limit :]:
            try:
                stale.unlink(missing_ok=True)
                logger.info("Pruned archive snapshot %s", stale)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.exception("Failed to prune snapshot %s", stale)

    def _emit_upcoming_highlights(self) -> None:
        """Send upcoming layered press summary to the opt-in channel."""

        if self._upcoming_publisher is None:
            return
        horizon_hours = 48
        upcoming = self.service.upcoming_press(limit=6, within_hours=horizon_hours)
        telemetry = get_telemetry()
        try:
            telemetry.track_queue_depth(len(upcoming), horizon_hours=horizon_hours)
        except Exception:  # pragma: no cover - telemetry failures shouldn't block highlights
            logger.exception("Failed to record queue depth telemetry")
        if not upcoming:
            return
        now = datetime.now(timezone.utc)
        lines = ["**Upcoming Highlights**"]
        for item in upcoming:
            release_at = item["release_at"]
            delta_minutes = max(0, int((release_at - now).total_seconds() // 60))
            if delta_minutes >= 60:
                hours = delta_minutes // 60
                minutes = delta_minutes % 60
                relative = f"{hours}h {minutes}m"
            else:
                relative = f"{delta_minutes}m"
            timestamp = release_at.strftime("%Y-%m-%d %H:%M UTC")
            badges = item.get("badges") or []
            label = f"[{" | ".join(badges)}] " if badges else ""
            lines.append(
                f"• {label}{item['headline']} — {timestamp} (in {relative})"
            )
        message = "\n".join(lines)
        try:
            self._upcoming_publisher(message)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to publish upcoming highlights")

    def _evaluate_alerts(self, *, duration_ms: float, release_count: int) -> None:
        """Check digest metrics against alert thresholds."""

        telemetry = get_telemetry()
        if self._alert_digest_ms and duration_ms > self._alert_digest_ms:
            message = (
                f"⚠️ Digest runtime {duration_ms:.0f}ms exceeded threshold "
                f"({self._alert_digest_ms:.0f}ms)."
            )
            self._notify_admin(message)
            telemetry.track_system_event(
                "alert_digest_slow",
                source="gazette_scheduler",
                reason=message,
            )
        queue_size = self.service.pending_press_count()
        if self._alert_queue_size and queue_size > self._alert_queue_size:
            message = (
                f"⚠️ Scheduled press backlog at {queue_size} items (threshold {self._alert_queue_size})."
            )
            self._notify_admin(message)
            telemetry.track_system_event(
                "alert_press_backlog",
                source="gazette_scheduler",
                reason=message,
            )
        if self._alert_release_min and release_count < self._alert_release_min:
            message = (
                f"⚠️ Digest published only {release_count} item(s); expected at least {self._alert_release_min}."
            )
            self._notify_admin(message)
            telemetry.track_system_event(
                "alert_low_digest_output",
                source="gazette_scheduler",
                reason=message,
            )


__all__ = ["GazetteScheduler"]
