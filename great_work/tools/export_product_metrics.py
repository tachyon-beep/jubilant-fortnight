"""Export product KPI snapshots for offline analysis."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ..telemetry import DEFAULT_TELEMETRY_DB, TelemetryCollector


def export_metrics(
    db_path: Path,
    *,
    output_dir: Path,
    include_history: bool = True,
    include_cohorts: bool = True,
) -> Dict[str, Any]:
    """Gather product KPI metrics and dump them to disk."""

    collector = TelemetryCollector(db_path)
    collector.flush()

    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "generated_at": now.isoformat(),
        "database": str(db_path),
        "product_kpis": collector.get_product_kpis(),
    }

    if include_history:
        payload["product_kpi_history"] = collector.get_product_kpi_history_summary()

    if include_cohorts:
        payload["engagement_cohorts"] = collector.get_engagement_cohorts()

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"product_metrics_{timestamp}.json"
    json_path.write_text(json.dumps(payload, indent=2))

    # Emit a lightweight CSV for quick spreadsheet import (active players focus).
    history = (
        payload.get("product_kpi_history", {}).get("daily", [])
        if include_history
        else []
    )
    csv_lines = [
        "date,active_players,manifesto_events,archive_events,nickname_events,press_share_events",
    ]
    for entry in history:
        csv_lines.append(
            "{date},{players},{manifesto},{archive},{nickname},{shares}".format(
                date=entry.get("date", ""),
                players=entry.get("active_players", 0.0),
                manifesto=entry.get("manifesto_events", 0.0),
                archive=entry.get("archive_events", 0.0),
                nickname=entry.get("nickname_events", 0.0),
                shares=entry.get("press_share_events", 0.0),
            )
        )
    csv_path = output_dir / f"product_metrics_{timestamp}.csv"
    csv_path.write_text("\n".join(csv_lines))

    return {
        "json": json_path,
        "csv": csv_path,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export product KPI metrics for offline analysis."
    )
    parser.add_argument(
        "--telemetry-db",
        type=Path,
        default=DEFAULT_TELEMETRY_DB,
        help=f"Path to telemetry SQLite database (default: {DEFAULT_TELEMETRY_DB}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("telemetry_exports"),
        help="Directory to write export files (default: telemetry_exports/).",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip exporting KPI history summary.",
    )
    parser.add_argument(
        "--no-cohorts",
        action="store_true",
        help="Skip exporting engagement cohort breakdown.",
    )
    return parser.parse_args()


def main() -> None:  # pragma: no cover - CLI wrapper
    args = _parse_args()
    export_metrics(
        args.telemetry_db,
        output_dir=args.output_dir,
        include_history=not args.no_history,
        include_cohorts=not args.no_cohorts,
    )


if __name__ == "__main__":
    main()
