"""Scheduler utilities for Gazette ticks."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .models import PressRelease
from .service import GameService

logger = logging.getLogger(__name__)


class GazetteScheduler:
    """Schedules Gazette digests and weekly symposium events."""

    def __init__(
        self,
        service: GameService,
        publisher: Optional[Callable[[PressRelease], None]] = None,
        admin_publisher: Optional[Callable[[str], None]] = None,
        admin_file_publisher: Optional[Callable[[Path, str], None]] = None,
    ) -> None:
        self.service = service
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()
        self._publisher = publisher
        self._admin_publisher = admin_publisher
        self._admin_file_publisher = admin_file_publisher

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
        if self.service.is_paused():
            message = self.service.pause_reason() or "Game is paused"
            self._notify_admin(f"⏸️ Digest skipped — {message}")
            self._emit_admin_notifications()
            return
        digest_releases = self.service.advance_digest()
        releases = digest_releases + self.service.resolve_pending_expeditions()
        if not releases:
            logger.info("No expeditions to report this digest")
            self._emit_admin_notifications()
            return
        for press in releases:
            self._emit_release(press)

        # Export web archive after digest
        try:
            archive_path = self.service.export_web_archive(Path("web_archive"), source="scheduler")
            logger.info(f"Web archive exported to {archive_path}")
            if self._admin_file_publisher is not None:
                snapshot_path = self._package_archive(archive_path)
                caption = f"📚 Web archive snapshot ready ({snapshot_path.name})"
                self._admin_file_publisher(snapshot_path, caption)
                logger.info("Web archive snapshot published to admin channel: %s", snapshot_path)
        except Exception:
            logger.exception("Failed to export web archive during digest")
        self._emit_admin_notifications()

    def _host_symposium(self) -> None:
        """Host weekly symposium with randomly selected topic."""
        # List of potential symposium topics
        topics = [
            ("The Nature of Truth", "Does objective truth exist in scientific inquiry, or is all knowledge relative to the observer?"),
            ("Ethics of Discovery", "Should there be limits on what knowledge humanity pursues?"),
            ("Collaboration vs Competition", "Does competition or collaboration lead to greater scientific advancement?"),
            ("The Role of Intuition", "What place does intuition have in rigorous academic work?"),
            ("Funding Priorities", "Should research funding favor practical applications or pure discovery?"),
            ("The Great Work Itself", "What is the true purpose of our collective academic endeavor?"),
            ("Knowledge Ownership", "Can ideas truly be owned, or does all knowledge belong to humanity?"),
            ("Academic Hierarchy", "Do traditional academic structures help or hinder progress?"),
        ]

        # Randomly select a topic
        import random
        topic, description = random.choice(topics)

        # Start the symposium
        press = self.service.start_symposium(topic, description)
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
        return Path(zip_file)


__all__ = ["GazetteScheduler"]
