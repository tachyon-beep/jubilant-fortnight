"""Scheduler utilities for Gazette ticks."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
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
    ) -> None:
        self.service = service
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()
        self._publisher = publisher

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
        digest_releases = self.service.advance_digest()
        releases = digest_releases + self.service.resolve_pending_expeditions()
        if not releases:
            logger.info("No expeditions to report this digest")
            return
        for press in releases:
            self._emit_release(press)

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

    def _emit_release(self, press: PressRelease) -> None:
        if self._publisher is not None:
            try:
                self._publisher(press)
                return
            except Exception:  # pragma: no cover - defensive logging only
                logger.exception("Failed to publish Gazette item")
        logger.info("%s\n%s", press.headline, press.body)


__all__ = ["GazetteScheduler"]
