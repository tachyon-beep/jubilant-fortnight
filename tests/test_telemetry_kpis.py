"""Telemetry KPI and cohort reporting tests."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from great_work.telemetry import MetricType, TelemetryCollector


def _age_metric(db_path: Path, player_id: str, command_name: str, delta_seconds: float) -> None:
    """Adjust the timestamp of the earliest matching metric by delta_seconds."""

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id
            FROM metrics
            WHERE metric_type = ?
              AND name = ?
              AND json_extract(tags, '$.player_id') = ?
            ORDER BY timestamp ASC
            LIMIT 1
            """,
            (MetricType.COMMAND_USAGE.value, command_name, player_id),
        ).fetchone()
        if not row:
            return
        conn.execute(
            "UPDATE metrics SET timestamp = timestamp - ? WHERE id = ?",
            (delta_seconds, row[0]),
        )
        conn.commit()


def test_engagement_cohorts_and_kpi_targets(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "telemetry.db"
    collector = TelemetryCollector(db_path)

    # Persist a canonical KPI target
    collector.set_kpi_target("active_players", 5, warning=3, notes="Playtest baseline")

    # Override environment thresholds to ensure DB target takes precedence
    monkeypatch.setenv("GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS", "2")

    # Returning player recorded long ago
    collector.record(
        MetricType.COMMAND_USAGE,
        "status",
        1.0,
        tags={"player_id": "alpha"},
        metadata={},
    )
    collector.flush()
    _age_metric(db_path, "alpha", "status", delta_seconds=10 * 86400)  # 10 days old

    # Same player issues fresh commands within the window
    collector.record(
        MetricType.COMMAND_USAGE,
        "symposium_vote",
        1.0,
        tags={"player_id": "alpha"},
        metadata={},
    )

    # New player only active within the window
    collector.record(
        MetricType.COMMAND_USAGE,
        "status",
        1.0,
        tags={"player_id": "beta"},
        metadata={},
    )

    # Symposium participation commands for both players
    collector.record(
        MetricType.COMMAND_USAGE,
        "symposium_status",
        1.0,
        tags={"player_id": "beta"},
        metadata={},
    )

    collector.flush()

    cohorts = collector.get_engagement_cohorts(days=7)
    assert cohorts["active_players"] == 2
    new_cohort = cohorts["cohorts"]["new"]
    returning_cohort = cohorts["cohorts"]["returning"]

    assert new_cohort["players"] == 1
    assert returning_cohort["players"] == 1
    assert any(player["player_id"] == "beta" for player in new_cohort["details"])
    assert any(player["player_id"] == "alpha" for player in returning_cohort["details"])

    kpi_targets = collector.get_kpi_targets()
    assert "active_players" in kpi_targets
    assert kpi_targets["active_players"]["target"] == pytest.approx(5)

    symposium = collector.get_symposium_metrics(hours=24)
    participation = symposium["participation"]
    assert participation["unique_players"] == 2
    assert participation["total_commands"] == pytest.approx(2.0)
    assert participation["by_command"]["symposium_vote"] == pytest.approx(1.0)

    report = collector.generate_report()
    assert "engagement_cohorts" in report
    assert "kpi_targets" in report
    assert report["kpi_targets"]["active_players"]["target"] == pytest.approx(5)
    assert report["health"]["thresholds"]["active_players"] == pytest.approx(5)
