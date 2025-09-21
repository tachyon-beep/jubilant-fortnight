"""Recommend KPI alert thresholds based on recorded telemetry data."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Tuple

from ..telemetry import MetricType, TelemetryCollector


def _bucket_daily(records: Iterable[Tuple[float, str]]) -> Dict[str, set[str]]:
    """Group player ids by UTC date (YYYY-MM-DD)."""

    buckets: Dict[str, set[str]] = defaultdict(set)
    for ts, player_id in records:
        day = _timestamp_to_day(ts)
        if day is None or not player_id:
            continue
        buckets[day].add(player_id)
    return buckets


def _timestamp_to_day(timestamp: float) -> str | None:
    from datetime import datetime, timezone

    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def _percent_floor(value: float, ratio: float, minimum: float = 0.0) -> float:
    """Return value scaled by ratio with a lower bound."""

    return max(minimum, value * ratio)


def recommend_thresholds(
    db_path: Path,
    *,
    engagement_days: int,
    manifesto_days: int,
    archive_days: int,
) -> Dict[str, float]:
    """Compute recommended KPI thresholds from telemetry history."""

    collector = TelemetryCollector(db_path)
    collector.flush()

    start_engagement = _window_start_seconds(engagement_days)
    start_manifesto = _window_start_seconds(manifesto_days)
    start_archive = _window_start_seconds(archive_days)

    with _connect(db_path) as conn:
        engagement_rows = list(
            conn.execute(
                """
                SELECT timestamp, json_extract(tags, '$.player_id')
                FROM metrics
                WHERE metric_type = ? AND timestamp >= ?
                """,
                (MetricType.COMMAND_USAGE.value, start_engagement),
            )
        )

        manifesto_rows = list(
            conn.execute(
                """
                SELECT json_extract(tags, '$.player_id')
                FROM metrics
                WHERE metric_type = ? AND name = ? AND timestamp >= ?
                """,
                (MetricType.GAME_PROGRESSION.value, "manifesto_generated", start_manifesto),
            )
        )

        archive_rows = list(
            conn.execute(
                """
                SELECT timestamp
                FROM metrics
                WHERE metric_type = ? AND name = ? AND timestamp >= ?
                """,
                (MetricType.GAME_PROGRESSION.value, "archive_lookup", start_archive),
            )
        )
        nickname_rows = list(
            conn.execute(
                """
                SELECT json_extract(tags, '$.player_id')
                FROM metrics
                WHERE metric_type = ? AND name = ? AND timestamp >= ?
                """,
                (MetricType.GAME_PROGRESSION.value, "nickname_adopted", start_manifesto),
            )
        )
        press_share_rows = list(
            conn.execute(
                """
                SELECT timestamp
                FROM metrics
                WHERE metric_type = ? AND name = ? AND timestamp >= ?
                """,
                (MetricType.GAME_PROGRESSION.value, "press_shared", start_archive),
            )
        )

    daily_players = _bucket_daily(engagement_rows)
    player_counts = [len(players) for players in daily_players.values()]

    if not player_counts:
        active_recommendation = 1.0
    else:
        average_players = statistics.mean(player_counts)
        floor_players = min(player_counts)
        active_recommendation = max(1.0, _percent_floor(average_players, 0.7))
        active_recommendation = min(active_recommendation, float(floor_players))

    active_player_total = len({player for players in daily_players.values() for player in players})
    manifesto_players = {row[0] for row in manifesto_rows if row and row[0]}

    manifesto_recommendation = 0.0
    nickname_recommendation = 0.0
    if active_player_total:
        adoption_ratio = len(manifesto_players) / active_player_total
        manifesto_recommendation = round(_percent_floor(adoption_ratio, 0.8), 2)
        nickname_ratio = len({row for row in nickname_rows if row and row[0]}) / active_player_total
        nickname_recommendation = round(_percent_floor(nickname_ratio, 0.8), 2)

    archive_events = len(archive_rows)
    if archive_events:
        archive_recommendation = max(1.0, _percent_floor(archive_events / archive_days, 0.5))
    else:
        archive_recommendation = 0.0

    press_share_events = len(press_share_rows)
    if press_share_events:
        press_share_recommendation = max(1.0, round(_percent_floor(press_share_events / archive_days, 0.6), 2))
    else:
        press_share_recommendation = 0.0

    return {
        "GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS": round(active_recommendation, 2),
        "GREAT_WORK_ALERT_MIN_MANIFESTO_RATE": round(manifesto_recommendation, 2),
        "GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS": round(archive_recommendation, 2),
        "GREAT_WORK_ALERT_MIN_NICKNAME_RATE": round(nickname_recommendation, 2),
        "GREAT_WORK_ALERT_MIN_PRESS_SHARES": round(press_share_recommendation, 2),
    }


def apply_thresholds(
    collector: TelemetryCollector,
    thresholds: Dict[str, float],
) -> Dict[str, Dict[str, float]]:
    """Persist recommendations into the KPI target table."""

    mappings = {
        "GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS": "active_players",
        "GREAT_WORK_ALERT_MIN_MANIFESTO_RATE": "manifesto_adoption",
        "GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS": "archive_usage",
        "GREAT_WORK_ALERT_MIN_NICKNAME_RATE": "nickname_rate",
        "GREAT_WORK_ALERT_MIN_PRESS_SHARES": "press_shares",
    }

    persisted: Dict[str, Dict[str, float]] = {}
    for env_key, target_name in mappings.items():
        value = thresholds.get(env_key)
        if value is None:
            continue
        collector.set_kpi_target(target_name, value)
        persisted[target_name] = {"target": value}
    return persisted


def _window_start_seconds(days: int) -> float:
    import time

    return time.time() - (days * 86400)


def _connect(db_path: Path):
    import sqlite3

    return sqlite3.connect(db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend KPI alert thresholds.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("telemetry.db"),
        help="Path to telemetry SQLite database (default: telemetry.db).",
    )
    parser.add_argument(
        "--engagement-days",
        type=int,
        default=7,
        help="Window (days) to analyse command usage.",
    )
    parser.add_argument(
        "--manifesto-days",
        type=int,
        default=14,
        help="Window (days) to analyse manifesto adoption.",
    )
    parser.add_argument(
        "--archive-days",
        type=int,
        default=14,
        help="Window (days) to analyse archive lookups.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist recommended thresholds into telemetry.kpi_targets.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write a JSON export of recommendations (and persisted targets when --apply is set).",
    )
    args = parser.parse_args()

    recommendations = recommend_thresholds(
        args.db,
        engagement_days=args.engagement_days,
        manifesto_days=args.manifesto_days,
        archive_days=args.archive_days,
    )

    applied: Dict[str, Dict[str, float]] = {}
    if args.apply:
        collector = TelemetryCollector(args.db)
        applied = apply_thresholds(collector, recommendations)

    if args.output:
        payload = {
            "recommendations": recommendations,
            "applied_targets": applied,
            "database": str(args.db),
        }
        args.output.write_text(json.dumps(payload, indent=2))

    # Print shell-friendly snippet regardless, so operators can copy/paste.
    print("# Recommended KPI thresholds (adjust as needed)")
    for key, value in recommendations.items():
        print(f"{key}={value}")

    if args.apply:
        print("\n# Applied targets")
        for name, payload in applied.items():
            target = payload.get("target")
            print(f" set target {name} => {target}")

    sys.exit(0)


if __name__ == "__main__":
    main()
