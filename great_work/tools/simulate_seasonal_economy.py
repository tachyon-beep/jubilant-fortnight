"""Seasonal economy/mentorship tuning simulator."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..analytics.calibration import collect_calibration_snapshot
from ..config import DEFAULT_STATE_DB, Settings
from ..service import GameService
from ..telemetry import TelemetryCollector


@dataclass
class CommitmentScenario:
    faction: str
    base_cost: Optional[int] = None
    duration_days: Optional[int] = None
    tier: Optional[str] = None


@dataclass
class PlayerScenario:
    player_id: str
    influence: Dict[str, int] = field(default_factory=dict)
    commitments: List[CommitmentScenario] = field(default_factory=list)


@dataclass
class SimulationConfig:
    days: int = 14
    players: List[PlayerScenario] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "SimulationConfig":
        players_payload = payload.get("players") or []
        players: List[PlayerScenario] = []
        for entry in players_payload:
            commitments = [
                CommitmentScenario(
                    faction=item["faction"],
                    base_cost=item.get("base_cost"),
                    duration_days=item.get("duration_days"),
                    tier=item.get("tier"),
                )
                for item in entry.get("commitments", [])
            ]
            players.append(
                PlayerScenario(
                    player_id=entry["player_id"],
                    influence={
                        k: int(v) for k, v in entry.get("influence", {}).items()
                    },
                    commitments=commitments,
                )
            )
        return cls(
            days=int(payload.get("days", 14)),
            players=players,
            settings=payload.get("settings", {}),
        )


def _apply_settings_overrides(
    settings: Settings, overrides: Dict[str, Any]
) -> Settings:
    valid_overrides = {
        key: value for key, value in overrides.items() if hasattr(settings, key)
    }
    if not valid_overrides:
        return settings
    return replace(settings, **valid_overrides)


def _seed_players(service: GameService, scenarios: Iterable[PlayerScenario]) -> None:
    for scenario in scenarios:
        service.ensure_player(scenario.player_id)
        player = service.state.get_player(scenario.player_id)
        if player is None:
            continue
        service._ensure_influence_structure(player)
        if scenario.influence:
            player.influence.update(scenario.influence)
            service.state.upsert_player(player)
        if scenario.commitments:
            for commitment in scenario.commitments:
                service.start_seasonal_commitment(
                    scenario.player_id,
                    faction=commitment.faction,
                    tier=commitment.tier,
                    base_cost=commitment.base_cost,
                    duration_days=commitment.duration_days,
                    allow_override=True,
                )


def run_simulation(
    *,
    base_db: Path,
    config: SimulationConfig,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a seasonal economy simulation returning timeline + summary."""

    sim_db = base_db.with_suffix(".seasonal_sim.db")
    if sim_db.exists():
        sim_db.unlink()
    service = GameService(sim_db)

    service.settings = _apply_settings_overrides(service.settings, config.settings)

    telemetry_path = sim_db.with_suffix(".telemetry.db")
    telemetry = TelemetryCollector(telemetry_path)
    service._telemetry = telemetry

    if not config.players:
        # Seed a default faction mix if none supplied.
        default_players = [
            PlayerScenario(
                player_id=f"player_{idx+1}",
                commitments=[CommitmentScenario(faction=faction)],
            )
            for idx, faction in enumerate(service._FACTIONS[:4])
        ]
        _seed_players(service, default_players)
    else:
        _seed_players(service, config.players)

    timeline: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for day in range(config.days):
        current_time = now + timedelta(days=day)
        releases = service._apply_seasonal_commitments(current_time)
        snapshot = collect_calibration_snapshot(
            service,
            telemetry,
            now=current_time,
            include_details=False,
        )
        seasonal_totals = snapshot.get("seasonal_commitments", {}).get("totals", {})
        economy_totals = snapshot.get("faction_investments", {}).get("totals", {})

        timeline.append(
            {
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
                "seasonal_totals": seasonal_totals,
                "investment_totals": economy_totals,
            }
        )

    summary = collect_calibration_snapshot(
        service,
        telemetry,
        now=now + timedelta(days=config.days),
        include_details=True,
    )

    result = {
        "config": {
            "days": config.days,
            "settings": config.settings,
            "players": [
                {
                    "player_id": player.player_id,
                    "influence": player.influence,
                    "commitments": [commit.__dict__ for commit in player.commitments],
                }
                for player in config.players
            ],
        },
        "timeline": timeline,
        "summary": summary,
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = output_dir / f"seasonal_simulation_{timestamp}.json"
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["output_path"] = str(output_path)

    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a seasonal economy tuning simulation."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_STATE_DB,
        help=f"Base database path for simulation state (default: {DEFAULT_STATE_DB}).",
    )
    parser.add_argument(
        "--config", type=Path, help="JSON file describing simulation scenario."
    )
    parser.add_argument(
        "--days", type=int, help="Simulation horizon in days (overrides config)."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("simulation_runs"))
    return parser.parse_args()


def main() -> None:  # pragma: no cover - CLI entry point
    args = _parse_args()
    config_payload = json.loads(args.config.read_text()) if args.config else {}
    config = SimulationConfig.from_mapping(config_payload)
    if args.days:
        config.days = args.days
    run_simulation(base_db=args.db, config=config, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
