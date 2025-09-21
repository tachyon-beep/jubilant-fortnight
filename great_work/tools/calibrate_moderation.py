"""Summarise moderation telemetry for threshold calibration."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from ..telemetry import DEFAULT_TELEMETRY_DB, MetricType, TelemetryCollector


def _load_events(collector: TelemetryCollector, hours: int) -> list[dict]:
    window_start = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    records: list[dict] = []

    import sqlite3

    with sqlite3.connect(collector.db_path) as conn:
        rows = conn.execute(
            """
                SELECT
                    name,
                    json_extract(tags, '$.stage') AS stage,
                    json_extract(tags, '$.surface') AS surface,
                    json_extract(tags, '$.severity') AS severity,
                    json_extract(tags, '$.actor') AS actor,
                    json_extract(tags, '$.text_hash') AS text_hash,
                    json_extract(tags, '$.source') AS source,
                    timestamp
                FROM metrics
                WHERE metric_type = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """,
            (MetricType.MODERATION.value, window_start),
        ).fetchall()
    for row in rows:
        records.append(
            {
                "category": row[0],
                "stage": row[1],
                "surface": row[2],
                "severity": row[3],
                "actor": row[4],
                "text_hash": row[5],
                "source": row[6],
                "timestamp": datetime.fromtimestamp(row[7], tz=timezone.utc).isoformat(),
            }
        )
    return records


def calibrate(collector: TelemetryCollector, *, hours: int) -> Dict[str, object]:
    events = _load_events(collector, hours)
    by_category = defaultdict(int)
    by_stage = defaultdict(int)
    by_severity = defaultdict(int)
    per_surface = defaultdict(int)

    for event in events:
        by_category[event["category"]] += 1
        by_stage[event["stage"]] += 1
        by_severity[event["severity"]] += 1
        per_surface[event["surface"]] += 1

    total = len(events)
    recommendation = {
        "hours": hours,
        "total_events": total,
        "by_category": dict(sorted(by_category.items(), key=lambda item: -item[1])),
        "by_stage": dict(sorted(by_stage.items(), key=lambda item: -item[1])),
        "by_severity": dict(sorted(by_severity.items(), key=lambda item: -item[1])),
        "top_surfaces": dict(sorted(per_surface.items(), key=lambda item: -item[1])[:10]),
        "recommendations": {
            "consider_lowering_thresholds": [
                category for category, count in by_category.items() if count / max(total, 1) > 0.3
            ],
            "stages_triggering_most": by_stage,
        },
        "events": events,
    }
    return recommendation


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise moderation telemetry for Guardian tuning.")
    parser.add_argument(
        "--telemetry-db",
        type=Path,
        default=DEFAULT_TELEMETRY_DB,
        help=f"Path to telemetry SQLite database (default: {DEFAULT_TELEMETRY_DB}).",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Hours of history to analyse (default: 168 hours / 7 days).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    collector = TelemetryCollector(args.telemetry_db)
    summary = calibrate(collector, hours=max(1, args.hours))
    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"Moderation events analysed: {summary['total_events']} in the last {summary['hours']}h")
    print("By severity:")
    for severity, count in summary["by_severity"].items():
        print(f"  - {severity}: {count}")
    print("Top categories:")
    for category, count in summary["by_category"].items():
        print(f"  - {category}: {count}")
    print("Top surfaces:")
    for surface, count in summary["top_surfaces"].items():
        print(f"  - {surface}: {count}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
