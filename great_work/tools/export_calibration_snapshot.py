"""CLI helper to export calibration snapshots for telemetry tuning."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..analytics import collect_calibration_snapshot, write_calibration_snapshot
from ..config import DEFAULT_STATE_DB, get_settings
from ..service import GameService
from ..telemetry import DEFAULT_TELEMETRY_DB, TelemetryCollector


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export calibration snapshot data.")
    parser.add_argument(
        "--state-db",
        type=Path,
        default=DEFAULT_STATE_DB,
        help=f"Path to the primary game state SQLite database (default: {DEFAULT_STATE_DB}).",
    )
    parser.add_argument(
        "--telemetry-db",
        type=Path,
        default=DEFAULT_TELEMETRY_DB,
        help=f"Path to the telemetry SQLite database (default: {DEFAULT_TELEMETRY_DB}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to write timestamped snapshots (default: print to stdout only).",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=12,
        help="How many historical snapshots to retain when writing to disk (default: 12).",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Exclude per-record details for a lighter snapshot payload.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Emit the snapshot JSON to stdout after writing (default when no output directory is provided).",
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        help="Override the timestamp used for the snapshot filename (ISO 8601).",
    )
    return parser.parse_args()


def _resolve_timestamp(timestamp: Optional[str]) -> datetime:
    if not timestamp:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError as exc:  # pragma: no cover - defensive parsing only
        raise SystemExit(f"Invalid --timestamp value: {timestamp}") from exc


def main() -> None:
    args = _parse_args()
    current_time = _resolve_timestamp(args.timestamp)

    settings = get_settings()
    service = GameService(
        args.state_db,
        settings=settings,
        auto_seed=False,
    )
    telemetry = TelemetryCollector(args.telemetry_db)

    include_details = not args.summary_only
    snapshot = collect_calibration_snapshot(
        service,
        telemetry,
        now=current_time,
        include_details=include_details,
    )

    if args.output_dir:
        output_dir = args.output_dir
        path = write_calibration_snapshot(
            service,
            telemetry,
            output_dir,
            now=current_time,
            include_details=include_details,
            keep_last=max(args.keep, 0),
            snapshot=snapshot,
        )
        if not args.stdout:
            print(str(path))
    if args.stdout or not args.output_dir:
        print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
