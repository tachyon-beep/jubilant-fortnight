"""Generate synthetic telemetry records for calibration dry runs."""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from ..telemetry import DEFAULT_TELEMETRY_DB, MetricEvent, MetricType, TelemetryCollector


def _append_event(
    telemetry: TelemetryCollector,
    *,
    timestamp: float,
    metric_type: MetricType,
    name: str,
    value: float,
    tags: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> None:
    event = MetricEvent(
        timestamp=timestamp,
        metric_type=metric_type,
        name=name,
        value=value,
        tags=tags or {},
        metadata=metadata or {},
    )
    telemetry._metrics_buffer.append(event)  # pylint: disable=protected-access


def _generate_day(
    telemetry: TelemetryCollector,
    *,
    day_offset: int,
    players: int,
    seed: int,
) -> None:
    rng = random.Random(seed + day_offset)
    day_start = datetime.now(timezone.utc) - timedelta(days=day_offset)

    for player_idx in range(players):
        player_id = f"player-{player_idx + 1:02d}"
        command_count = rng.randint(2, 8)
        base_ts = day_start.replace(hour=8, minute=0, second=0, microsecond=0)
        for cmd in range(command_count):
            ts = base_ts + timedelta(minutes=cmd * 10)
            _append_event(
                telemetry,
                timestamp=ts.timestamp(),
                metric_type=MetricType.COMMAND_USAGE,
                name="slash_command",
                value=1.0,
                tags={"player_id": player_id, "command": rng.choice(["wager", "recruit", "status", "symposium_vote"])},
            )

        if rng.random() < 0.4:
            ts = base_ts + timedelta(hours=1)
            _append_event(
                telemetry,
                timestamp=ts.timestamp(),
                metric_type=MetricType.GAME_PROGRESSION,
                name="manifesto_generated",
                value=1.0,
                tags={"player_id": player_id},
            )
        if rng.random() < 0.3:
            ts = base_ts + timedelta(hours=2)
            _append_event(
                telemetry,
                timestamp=ts.timestamp(),
                metric_type=MetricType.GAME_PROGRESSION,
                name="archive_lookup",
                value=1.0,
                tags={},
            )
        if rng.random() < 0.2:
            ts = base_ts + timedelta(hours=3)
            _append_event(
                telemetry,
                timestamp=ts.timestamp(),
                metric_type=MetricType.GAME_PROGRESSION,
                name="nickname_adopted",
                value=1.0,
                tags={"player_id": player_id},
            )
        if rng.random() < 0.15:
            ts = base_ts + timedelta(hours=4)
            _append_event(
                telemetry,
                timestamp=ts.timestamp(),
                metric_type=MetricType.GAME_PROGRESSION,
                name="press_shared",
                value=1.0,
                tags={"player_id": player_id},
            )

        economy_total = rng.randint(5, 25)
        _append_event(
            telemetry,
            timestamp=day_start.replace(hour=20, minute=0, second=0, microsecond=0).timestamp(),
            metric_type=MetricType.ECONOMY_BALANCE,
            name=rng.choice(["faction_academia", "faction_government", "faction_industry"]),
            value=float(economy_total),
            metadata={"player_count": players, "avg_per_player": economy_total / max(players, 1)},
        )


def generate(
    telemetry_db: Path,
    *,
    players: int,
    days: int,
    seed: int,
) -> None:
    telemetry = TelemetryCollector(telemetry_db)
    for day in range(days):
        _generate_day(telemetry, day_offset=day, players=players, seed=seed)
    telemetry.flush()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic telemetry data for calibration tests.")
    parser.add_argument(
        "--telemetry-db",
        type=Path,
        default=DEFAULT_TELEMETRY_DB,
        help=f"Path to telemetry SQLite database (default: {DEFAULT_TELEMETRY_DB}).",
    )
    parser.add_argument(
        "--players",
        type=int,
        default=6,
        help="Number of synthetic players to simulate (default: 6).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of historical days to generate (default: 7).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for the pseudo-random generator (default: 42).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    generate(
        args.telemetry_db,
        players=max(1, args.players),
        days=max(1, args.days),
        seed=args.seed,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
