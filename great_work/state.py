"""Game state management and persistence."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Event, Player, Scholar
from .scholars import ScholarRepository

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    reputation INTEGER NOT NULL,
    influence TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scholars (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class GameState:
    """High level interface for working with persistent state."""

    def __init__(self, db_path: Path, repository: ScholarRepository | None = None) -> None:
        self._db_path = db_path
        self._repo = repository or ScholarRepository()
        self._ensure_schema()
        self._cached_players: Dict[str, Player] = {}
        self._cached_scholars: Dict[str, Scholar] = {}

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.executescript(_DB_SCHEMA)
            conn.commit()

    # Player management -------------------------------------------------
    def upsert_player(self, player: Player) -> None:
        influence_json = json.dumps(player.influence)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "REPLACE INTO players (id, display_name, reputation, influence) VALUES (?, ?, ?, ?)",
                (player.id, player.display_name, player.reputation, influence_json),
            )
            conn.commit()
        self._cached_players[player.id] = player

    def get_player(self, player_id: str) -> Optional[Player]:
        if player_id in self._cached_players:
            return self._cached_players[player_id]
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT id, display_name, reputation, influence FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not row:
                return None
            influence = json.loads(row[3])
            player = Player(id=row[0], display_name=row[1], reputation=row[2], influence=influence)
            self._cached_players[player.id] = player
            return player

    def all_players(self) -> Iterable[Player]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute("SELECT id, display_name, reputation, influence FROM players").fetchall()
        for row in rows:
            influence = json.loads(row[3])
            player = Player(id=row[0], display_name=row[1], reputation=row[2], influence=influence)
            self._cached_players[player.id] = player
            yield player

    # Scholar management ------------------------------------------------
    def seed_base_scholars(self) -> None:
        for scholar in self._repo.base_scholars():
            self.save_scholar(scholar)

    def save_scholar(self, scholar: Scholar) -> None:
        data_json = json.dumps(self._repo.serialize(scholar))
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("REPLACE INTO scholars (id, data) VALUES (?, ?)", (scholar.id, data_json))
            conn.commit()
        self._cached_scholars[scholar.id] = scholar

    def get_scholar(self, scholar_id: str) -> Optional[Scholar]:
        if scholar_id in self._cached_scholars:
            return self._cached_scholars[scholar_id]
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute("SELECT data FROM scholars WHERE id = ?", (scholar_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        scholar = self._repo.from_dict(data)
        self._cached_scholars[scholar.id] = scholar
        return scholar

    def all_scholars(self) -> Iterable[Scholar]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute("SELECT data FROM scholars").fetchall()
        for row in rows:
            data = json.loads(row[0])
            scholar = self._repo.from_dict(data)
            self._cached_scholars[scholar.id] = scholar
            yield scholar

    # Event log ---------------------------------------------------------
    def append_event(self, event: Event) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO events (timestamp, action, payload) VALUES (?, ?, ?)",
                (event.timestamp.isoformat(), event.action, json.dumps(event.payload)),
            )
            conn.commit()

    def export_events(self) -> List[Event]:
        events: List[Event] = []
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT timestamp, action, payload FROM events ORDER BY id ASC"
            ).fetchall()
        for ts, action, payload in rows:
            events.append(
                Event(
                    timestamp=datetime.fromisoformat(ts),
                    action=action,
                    payload=json.loads(payload),
                )
            )
        return events


__all__ = ["GameState"]
