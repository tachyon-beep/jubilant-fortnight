"""Scheduler utilities for Gazette ticks."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .config import get_settings
from .service import GameService

logger = logging.getLogger(__name__)


class GazetteScheduler:
    """Schedules Gazette digests and weekly symposium events."""

    def __init__(self, service: GameService) -> None:
        self.service = service
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()

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
            logger.info("%s\n%s", press.headline, press.body)

    def _host_symposium(self) -> None:
        logger.info("Symposium event triggered at %s", datetime.now(timezone.utc).isoformat())


__all__ = ["GazetteScheduler"]
