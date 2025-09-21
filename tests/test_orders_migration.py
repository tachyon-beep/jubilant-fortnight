from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest import mock

from great_work.config import get_settings
from great_work.state import GameState
from great_work.tools import manage_orders


def _init_state(tmp_path: Path) -> GameState:
    settings = get_settings()
    state_db = tmp_path / "state.db"
    return GameState(state_db, start_year=settings.timeline_start_year)


def _seed_legacy_followup(state: GameState, *, scholar_id: str, kind: str, resolve_at: str) -> None:
    with sqlite3.connect(state._db_path) as conn:  # pylint: disable=protected-access
        conn.execute(
            "INSERT INTO followups (scholar_id, kind, payload, resolve_at) VALUES (?, ?, ?, ?)",
            (scholar_id, kind, json.dumps({"note": "legacy"}), resolve_at),
        )
        conn.commit()


def test_preview_and_migrate_followups(tmp_path) -> None:
    state = _init_state(tmp_path)
    now_iso = "2030-01-01T12:00:00+00:00"
    _seed_legacy_followup(state, scholar_id="s-1", kind="defection_grudge", resolve_at=now_iso)

    preview = state.preview_followup_migration()
    assert preview["pending_rows"] == 1
    assert preview["kinds"] == {"defection_grudge": 1}

    result = state.migrate_followups()
    assert result["migrated"] is True
    assert result["migrated_rows"] == 1
    assert result["existing_orders"]["by_status"].get("pending", 0) == 1

    orders = [order for order in state.list_orders(order_type="followup:defection_grudge")]
    assert len(orders) == 1
    payload = orders[0]["payload"]
    assert payload["note"] == "legacy"


def test_manage_orders_summary(tmp_path, capsys) -> None:
    state = _init_state(tmp_path)
    # Enqueue a sample order
    state.enqueue_order(
        "mentorship_activation",
        actor_id="player-1",
        subject_id="scholar-1",
        payload={"scholar_id": "scholar-1"},
    )

    parser = manage_orders.build_parser()
    args = parser.parse_args(["--state-db", str(state._db_path), "summary", "--json"])  # pylint: disable=protected-access
    with mock.patch.object(manage_orders, "print") as mock_print:
        args.func(args)
    assert mock_print.call_count == 1
    payload = json.loads(mock_print.call_args.args[0])
    assert payload["total"] == 1
    assert payload["by_type"] == {"mentorship_activation": 1}
