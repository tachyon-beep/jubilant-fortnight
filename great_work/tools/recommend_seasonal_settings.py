"""Recommend seasonal commitment tuning values from telemetry."""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path
from typing import Dict

from ..telemetry import DEFAULT_TELEMETRY_DB, MetricType, TelemetryCollector


def recommend_settings(db_path: Path, days: int = 30) -> Dict[str, float]:
    """Return heuristic seasonal commitment tuning recommendations."""

    import sqlite3
    import time

    collector = TelemetryCollector(db_path)
    collector.flush()

    window_start = time.time() - days * 86400

    with sqlite3.connect(db_path) as conn:
        rows = list(
            conn.execute(
                """
                    SELECT timestamp,
                           value,
                           json_extract(tags, '$.player_id') as player_id,
                           json_extract(metadata, '$.remaining_debt') as remaining_debt,
                           json_extract(metadata, '$.threshold') as threshold,
                           json_extract(metadata, '$.days_remaining') as days_remaining
                    FROM metrics
                    WHERE metric_type = ? AND name = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """,
                (
                    MetricType.GAME_PROGRESSION.value,
                    "seasonal_commitment_status",
                    window_start,
                ),
            )
        )

    latest_per_player: Dict[str, Dict[str, float]] = {}
    for ts, value, player_id, remaining, threshold, days_remaining in rows:
        player_key = str(player_id or "unknown")
        debt = float(remaining if remaining is not None else value or 0.0)
        latest_per_player[player_key] = {
            "debt": debt,
            "threshold": float(threshold or 0.0),
            "days_remaining": float(days_remaining or 0.0),
        }

    outstanding = [
        entry["debt"] for entry in latest_per_player.values() if entry["debt"] > 0
    ]
    thresholds = [
        entry["threshold"]
        for entry in latest_per_player.values()
        if entry["threshold"] > 0
    ]
    days_remaining = [
        entry["days_remaining"]
        for entry in latest_per_player.values()
        if entry["days_remaining"] > 0
    ]

    if outstanding:
        avg_debt = statistics.mean(outstanding)
        median_debt = statistics.median(outstanding)
        total_debt = sum(outstanding)
    else:
        avg_debt = median_debt = total_debt = 0.0

    median_threshold = statistics.median(thresholds) if thresholds else 4.0
    median_days_remaining = (
        statistics.median(days_remaining) if days_remaining else 14.0
    )

    suggested_base_cost = max(1.0, round(median_debt / 4.0, 1)) if median_debt else 3.0
    suggested_reprisal_threshold = (
        max(2.0, round((median_debt / max(suggested_base_cost, 1.0)) + 1.0))
        if median_debt
        else median_threshold
    )
    suggested_alert = max(10.0, round(total_debt * 1.25, 1)) if total_debt else 10.0

    return {
        "average_debt": round(avg_debt, 2),
        "median_debt": round(median_debt, 2),
        "median_threshold": round(median_threshold, 2),
        "median_days_remaining": round(median_days_remaining, 1),
        "suggested_base_cost": round(suggested_base_cost, 1),
        "suggested_reprisal_threshold": round(suggested_reprisal_threshold, 1),
        "suggested_alert": round(suggested_alert, 1),
        "players_sampled": len(latest_per_player),
        "window_days": days,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recommend seasonal commitment tuning values."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_TELEMETRY_DB,
        help=f"Path to telemetry database (default: {DEFAULT_TELEMETRY_DB}).",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Lookback window in days (default: 30)"
    )
    args = parser.parse_args()

    recommendations = recommend_settings(args.db, days=args.days)

    print("# Seasonal commitment summary")
    print(
        f"Players sampled: {recommendations['players_sampled']} (window {recommendations['window_days']}d)"
    )
    print(f"Average outstanding debt: {recommendations['average_debt']}")
    print(f"Median outstanding debt: {recommendations['median_debt']}")
    print(f"Median reprisal threshold observed: {recommendations['median_threshold']}")
    print(f"Median days remaining: {recommendations['median_days_remaining']}")
    print("\n# Recommended settings (adjust as needed)")
    print(f"seasonal_commitments.base_cost ≈ {recommendations['suggested_base_cost']}")
    print(
        f"seasonal_commitments.reprisal_threshold ≈ {recommendations['suggested_reprisal_threshold']}"
    )
    print(f"GREAT_WORK_ALERT_MAX_SEASONAL_DEBT ≈ {recommendations['suggested_alert']}")


if __name__ == "__main__":
    main()
