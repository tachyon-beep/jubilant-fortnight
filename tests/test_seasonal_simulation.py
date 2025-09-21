"""Tests for the seasonal economy simulation harness."""
from __future__ import annotations

import json
from pathlib import Path

from great_work.tools import simulate_seasonal_economy


def test_simulate_seasonal_economy_generates_timeline(tmp_path: Path) -> None:
    db_path = tmp_path / "scratch.db"
    result = simulate_seasonal_economy.run_simulation(
        db_path=db_path,
        config=simulate_seasonal_economy.SimulationConfig(players=2, days=3),
    )

    assert "timeline" in result
    assert len(result["timeline"]) == 3
    assert result["timeline"][0]["day"] == 0


def test_simulation_cli(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "out.json"
    monkeypatch.setattr(
        simulate_seasonal_economy,
        "_parse_args",
        lambda: type("Args", (), {"db": tmp_path / "baseline.db", "players": 1, "days": 1, "output": output})(),
    )

    simulate_seasonal_economy.main()

    payload = json.loads(output.read_text())
    assert payload["config"]["players"] == 1
