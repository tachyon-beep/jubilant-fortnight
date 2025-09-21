"""Simulate seasonal commitments and mentorship tuning scenarios."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..service import GameService
from ..settings import Settings


@dataclass
class SimulationConfig:
    """Top-level configuration for a seasonal economy simulation."""

    players: int = 4
    days: int = 14
    seed: int = 42
    seasonal_base_cost: int = 4
    seasonal_duration_days: int = 28
    seasonal_reprisal_threshold: int = 12
    seasonal_reprisal_penalty: int = 4
    seasonal_reprisal_cooldown_days: int = 7
    mentorship_decay: float = 0.98
    mentorship_bonus: float = 0.75


def _apply_overrides(settings: Settings, config: SimulationConfig) -> None:
    """Clone settings and apply override parameters for a simulation run."""

    settings.seasonal_commitment_base_cost = config.seasonal_base_cost
    settings.seasonal_commitment_duration_days = config.seasonal_duration_days
    settings.seasonal_commitment_reprisal_threshold = config.seasonal_reprisal_threshold
    settings.seasonal_commitment_reprisal_penalty = config.seasonal_reprisal_penalty
    settings.seasonal_commitment_reprisal_cooldown_days = config.seasonal_reprisal_cooldown_days
    settings.mentorship_decay = config.mentorship_decay
    settings.mentorship_bonus = config.mentorship_bonus


def run_simulation(
    *,
    db_path: Path,
    config: SimulationConfig,
    settings: Optional[Settings] = None,
) -> Dict[str, object]:
    """Run a deterministic seasonal economy simulation."""

    # Create a fresh game service using a scratch database.
    sim_db = db_path.with_suffix(".sim.db")
    if sim_db.exists():
        sim_db.unlink()
    service = GameService(sim_db)

    if settings is None:
        settings = service.settings
    else:
        service.settings = settings

    _apply_overrides(service.settings, config)

    # Seed players and commitments
    for idx in range(config.players):
        player_id = f"player_{idx+1}"
        service.ensure_player(player_id)
        faction = service._FACTIONS[idx % len(service._FACTIONS)]  # Demonstrating coverage
        service.start_seasonal_commitment(
            player_id,
            faction=faction,
            allow_override=True,
        )

    now = datetime.now(timezone.utc)
    timeline: List[Dict[str, object]] = []
    for day in range(config.days):
        current_time = now + timedelta(days=day)
        releases = service._apply_seasonal_commitments(current_time)
        summary = {
            "day": day,
            "timestamp": current_time.isoformat(),
            "releases": [
                {
                    "headline": press.headline,
                    "type": press.type,
                    "metadata": press.metadata,
                }
                for press in releases
            ],
        }
        timeline.append(summary)

    result = {
        "config": config.__dict__,
        "timeline": timeline,
    }
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate seasonal commitments and mentorship tuning scenarios.")
    parser.add_argument("--db", type=Path, default=Path("great_work.db"), help="Base database to sample players from.")
    parser.add_argument("--players", type=int, default=4)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--output", type=Path, default=Path("simulation_output.json"))
    return parser.parse_args()


def main() -> None:  # pragma: no cover - CLI entry-point
    args = _parse_args()
    config = SimulationConfig(players=args.players, days=args.days)
    payload = run_simulation(db_path=args.db, config=config)
    args.output.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

