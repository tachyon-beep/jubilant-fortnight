from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from great_work.analytics import collect_calibration_snapshot, write_calibration_snapshot
from great_work.config import get_settings
from great_work.models import Player
from great_work.service import GameService
from great_work.state import GameState
from great_work.telemetry import TelemetryCollector


def _init_state(path: Path) -> tuple[GameState, Player]:
    settings = get_settings()
    state = GameState(path, start_year=settings.timeline_start_year)
    player = Player(
        id="player-1",
        display_name="Player One",
        reputation=5,
        influence={"academia": 20, "government": 10},
    )
    state.upsert_player(player)
    return state, player


def test_collect_calibration_snapshot(tmp_path) -> None:
    settings = get_settings()
    state_db = tmp_path / "state.db"
    state, player = _init_state(state_db)

    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=1)
    end_at = now + timedelta(days=settings.seasonal_commitment_duration_days)
    state.create_seasonal_commitment(
        player_id=player.id,
        faction="academia",
        tier="silver",
        base_cost=12,
        start_at=start_at,
        end_at=end_at,
    )
    state.record_influence_debt(
        player_id=player.id,
        faction="academia",
        amount=3,
        now=now,
        source="seasonal",
    )

    state.record_faction_investment(
        player_id=player.id,
        faction="government",
        amount=15,
        program="library-wing",
        created_at=now - timedelta(days=2),
    )
    state.record_archive_endowment(
        player_id=player.id,
        faction="academia",
        amount=25,
        program="digital-archive",
        created_at=now - timedelta(days=3),
    )

    state.enqueue_order(
        "mentorship_activation",
        payload={"scholar_id": "s.proc-001"},
        actor_id=player.id,
        scheduled_at=now + timedelta(hours=6),
    )

    telemetry_db = tmp_path / "telemetry.db"
    telemetry = TelemetryCollector(telemetry_db)
    telemetry.track_command("status", player.id, "guild-1")
    telemetry.flush()

    service = GameService(state_db, settings=settings, auto_seed=False)
    snapshot = collect_calibration_snapshot(
        service,
        telemetry,
        now=now,
    )

    seasonal_totals = snapshot["seasonal_commitments"]["totals"]
    assert seasonal_totals["active"] == 1
    assert seasonal_totals["outstanding_debt"] == 3

    investments_total = snapshot["faction_investments"]["totals"]["amount"]
    assert investments_total == 15

    endowments_total = snapshot["archive_endowments"]["totals"]["amount"]
    assert endowments_total == 25

    orders_total = snapshot["orders"]["totals"]["pending"]
    assert orders_total == 1

    output_dir = tmp_path / "snapshots"
    output_path = write_calibration_snapshot(
        service,
        telemetry,
        output_dir,
        now=now,
        keep_last=1,
        snapshot=snapshot,
    )
    assert output_path.exists()
    latest_path = output_dir / "latest.json"
    assert latest_path.exists()

    # Ensure pruning retains only latest snapshot when limit is 1
    second_path = write_calibration_snapshot(
        service,
        telemetry,
        output_dir,
        now=now + timedelta(minutes=5),
        keep_last=1,
    )
    files = sorted(output_dir.glob("calibration_snapshot_*.json"))
    assert len(files) == 1
    assert files[0] == second_path
