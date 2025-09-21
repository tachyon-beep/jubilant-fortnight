"""Tests for GazetteScheduler archive publishing and retention."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from great_work.scheduler import GazetteScheduler


class DummyService:
    """Minimal service stub for scheduler unit tests."""

    def __init__(self) -> None:
        self._notifications: list[str] = []

    def drain_admin_notifications(self) -> list[str]:
        return []

    def pending_press_count(self) -> int:  # pragma: no cover - simple stub
        return 0

    def upcoming_press(
        self, *, limit: int = 5, within_hours: int = 48
    ) -> list[dict]:  # pragma: no cover - stub
        return []

    def create_digest_highlights(
        self, *, now=None, limit: int = 5, within_hours: int = 24
    ):  # pragma: no cover - stub
        return None


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_PUBLISH_DIR", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_PAGES_DIR", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_PAGES_SUBDIR", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_PAGES_NOJEKYLL", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_PAGES_ENABLED", raising=False)
    monkeypatch.delenv("GREAT_WORK_ARCHIVE_MAX_STORAGE_MB", raising=False)
    yield


def test_publish_to_container_syncs_files(tmp_path, monkeypatch):
    """Archive publishing should mirror the export directory into the container volume."""

    publish_dir = tmp_path / "publish"
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "index.html").write_text("hello", encoding="utf-8")

    monkeypatch.setenv("GREAT_WORK_ARCHIVE_PUBLISH_DIR", str(publish_dir))

    scheduler = GazetteScheduler(service=DummyService())
    scheduler._publish_to_container(export_dir)

    published = publish_dir / "index.html"
    assert published.exists()
    assert published.read_text(encoding="utf-8") == "hello"


def test_prune_snapshots_enforces_limit(tmp_path, monkeypatch):
    """Snapshot pruning should keep only the newest archives."""

    monkeypatch.setenv("GREAT_WORK_ARCHIVE_PUBLISH_DIR", str(tmp_path / "publish"))
    monkeypatch.setenv("GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS", "2")

    scheduler = GazetteScheduler(service=DummyService())

    snapshots_dir = tmp_path / "snapshots"
    snapshots_dir.mkdir()

    for idx in range(3):
        path = snapshots_dir / f"web_archive_2024010{idx}.zip"
        path.write_bytes(b"stub")
        timestamp = time.time() + idx
        os.utime(path, (timestamp, timestamp))

    scheduler._prune_snapshots(snapshots_dir)

    remaining = sorted(snapshots_dir.glob("web_archive_*.zip"))
    assert len(remaining) == 2
    # Newest files should remain (highest idx values)
    assert remaining[-1].name.endswith("2.zip")


def test_queue_depth_tracked_in_upcoming_highlights(monkeypatch):
    """Upcoming highlights should record queue depth telemetry."""

    calls: list[tuple[int, int]] = []

    class TrackingTelemetry:
        def track_queue_depth(self, queue_size: int, *, horizon_hours: int) -> None:
            calls.append((queue_size, horizon_hours))

    monkeypatch.setenv("GREAT_WORK_CHANNEL_UPCOMING", "123")
    monkeypatch.setattr(
        "great_work.scheduler.get_telemetry", lambda: TrackingTelemetry()
    )

    class UpcomingService(DummyService):
        def upcoming_press(
            self, *, limit: int = 5, within_hours: int = 48
        ) -> list[dict]:
            return [
                {
                    "headline": "Scheduled Layer",
                    "type": "academic_gossip",
                    "release_at": datetime.now(timezone.utc) + timedelta(minutes=30),
                }
            ]

        def create_digest_highlights(
            self, *, now=None, limit: int = 5, within_hours: int = 24
        ):
            return None

    messages: list[str] = []

    scheduler = GazetteScheduler(
        service=UpcomingService(),
        upcoming_publisher=lambda message: messages.append(message),
    )

    scheduler._emit_upcoming_highlights()

    assert calls == [(1, 48)]
    assert messages  # ensures publisher fired


def test_publish_to_pages_syncs_repository(tmp_path, monkeypatch):
    """GitHub Pages publishing should mirror the archive into the configured repo."""

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "index.html").write_text("hello pages", encoding="utf-8")

    pages_dir = tmp_path / "pages_repo"
    monkeypatch.setenv("GREAT_WORK_ARCHIVE_PAGES_DIR", str(pages_dir))

    scheduler = GazetteScheduler(service=DummyService())
    scheduler._publish_to_pages(export_dir)

    published = pages_dir / "archive" / "index.html"
    assert published.exists()
    assert published.read_text(encoding="utf-8") == "hello pages"
    assert (pages_dir / ".nojekyll").exists()


def test_package_archive_emits_storage_alert(tmp_path, monkeypatch):
    """Snapshot packaging should alert when storage usage crosses configured limit."""

    monkeypatch.setenv("GREAT_WORK_ARCHIVE_MAX_STORAGE_MB", "0.0001")

    events: list[tuple[str, str | None, str | None]] = []

    class TrackingTelemetry:
        def track_system_event(
            self, event: str, *, source: str | None = None, reason: str | None = None
        ) -> None:
            events.append((event, source, reason))

    monkeypatch.setattr(
        "great_work.scheduler.get_telemetry", lambda: TrackingTelemetry()
    )

    messages: list[str] = []

    scheduler = GazetteScheduler(
        service=DummyService(),
        admin_publisher=lambda message: messages.append(message),
    )

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "data.bin").write_bytes(os.urandom(4096))

    scheduler._package_archive(export_dir)

    assert any("Archive snapshots now consume" in message for message in messages)
    assert any(event == "archive_snapshot_usage_exceeded" for event, _, _ in events)
