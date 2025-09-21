"""Tests for the seasonal economy tuning simulator."""
from __future__ import annotations

import json
from pathlib import Path

from great_work.tools.simulate_seasonal_economy import (
    CommitmentScenario,
    PlayerScenario,
    SimulationConfig,
    run_simulation,
)


def build_config() -> SimulationConfig:
    return SimulationConfig(
        days=3,
        players=[
            PlayerScenario(
                player_id="alpha",
                influence={"academia": 12},
                commitments=[CommitmentScenario(faction="academia", base_cost=4)],
            ),
            PlayerScenario(
                player_id="beta",
                influence={"industry": 10},
                commitments=[CommitmentScenario(faction="industry", base_cost=3)],
            ),
        ],
        settings={
            "seasonal_commitment_reprisal_threshold": 6,
            "seasonal_commitment_reprisal_penalty": 2,
        },
    )


def test_run_simulation_generates_summary(tmp_path: Path) -> None:
    config = build_config()
    result = run_simulation(base_db=tmp_path / "base.db", config=config)

    assert "timeline" in result
    assert len(result["timeline"]) == config.days
    summary = result["summary"]
    assert "seasonal_commitments" in summary


def test_cli_output(tmp_path: Path, monkeypatch) -> None:
    config = build_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
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
    }))

    def fake_parse_args():
        return type(
            "Args",
            (),
            {
                "db": tmp_path / "cli.db",
                "config": config_path,
                "days": None,
                "output_dir": tmp_path / "runs",
            },
        )()

    from great_work.tools import simulate_seasonal_economy

    monkeypatch.setattr(simulate_seasonal_economy, "_parse_args", fake_parse_args)
    simulate_seasonal_economy.main()

    output_files = list((tmp_path / "runs").glob("seasonal_simulation_*.json"))
    assert output_files, "Expected CLI to produce an output file"
