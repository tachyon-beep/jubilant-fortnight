"""Game state management and persistence."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    Event,
    ExpeditionRecord,
    Player,
    PressRecord,
    PressRelease,
    Scholar,
    TheoryRecord,
)
from .scholars import ScholarRepository

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    reputation INTEGER NOT NULL,
    influence TEXT NOT NULL,
    cooldowns TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS theories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    player_id TEXT NOT NULL,
    theory TEXT NOT NULL,
    confidence TEXT NOT NULL,
    supporters TEXT NOT NULL,
    deadline TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expeditions (
    code TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    player_id TEXT NOT NULL,
    expedition_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    team TEXT NOT NULL,
    funding TEXT NOT NULL,
    prep_depth TEXT NOT NULL,
    confidence TEXT NOT NULL,
    outcome TEXT,
    reputation_delta INTEGER NOT NULL DEFAULT 0,
    result_payload TEXT
);
CREATE TABLE IF NOT EXISTS press_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    type TEXT NOT NULL,
    headline TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relationships (
    scholar_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    feeling REAL NOT NULL,
    PRIMARY KEY (scholar_id, subject_id)
);
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id TEXT NOT NULL,
    faction TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scholar_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    resolve_at TEXT NOT NULL
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
        cooldowns_json = json.dumps(player.cooldowns)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "REPLACE INTO players (id, display_name, reputation, influence, cooldowns) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    player.id,
                    player.display_name,
                    player.reputation,
                    influence_json,
                    cooldowns_json,
                ),
            )
            conn.commit()
        self._cached_players[player.id] = player

    def get_player(self, player_id: str) -> Optional[Player]:
        if player_id in self._cached_players:
            return self._cached_players[player_id]
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT id, display_name, reputation, influence, cooldowns FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            if not row:
                return None
            influence = json.loads(row[3])
            cooldowns = json.loads(row[4])
            player = Player(
                id=row[0],
                display_name=row[1],
                reputation=row[2],
                influence=influence,
                cooldowns=cooldowns,
            )
            self._cached_players[player.id] = player
            return player

    def all_players(self) -> Iterable[Player]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT id, display_name, reputation, influence, cooldowns FROM players"
            ).fetchall()
        for row in rows:
            influence = json.loads(row[3])
            cooldowns = json.loads(row[4])
            player = Player(
                id=row[0],
                display_name=row[1],
                reputation=row[2],
                influence=influence,
                cooldowns=cooldowns,
            )
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

    def remove_scholar(self, scholar_id: str) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("DELETE FROM scholars WHERE id = ?", (scholar_id,))
            conn.execute("DELETE FROM relationships WHERE scholar_id = ? OR subject_id = ?", (scholar_id, scholar_id))
            conn.execute("DELETE FROM followups WHERE scholar_id = ?", (scholar_id,))
            conn.commit()
        self._cached_scholars.pop(scholar_id, None)

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

    # Relationship management -------------------------------------------
    def update_relationship(self, scholar_id: str, subject_id: str, feeling: float) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "REPLACE INTO relationships (scholar_id, subject_id, feeling) VALUES (?, ?, ?)",
                (scholar_id, subject_id, feeling),
            )
            conn.commit()

    def get_relationship(self, scholar_id: str, subject_id: str) -> Optional[float]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT feeling FROM relationships WHERE scholar_id = ? AND subject_id = ?",
                (scholar_id, subject_id),
            ).fetchone()
        if not row:
            return None
        return float(row[0])

    # Event log ---------------------------------------------------------
    def append_event(self, event: Event) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO events (timestamp, action, payload) VALUES (?, ?, ?)",
                (event.timestamp.isoformat(), event.action, json.dumps(event.payload)),
            )
            conn.commit()

    # Follow-up queue ---------------------------------------------------
    def schedule_followup(
        self, scholar_id: str, kind: str, resolve_at: datetime, payload: Dict[str, object]
    ) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO followups (scholar_id, kind, payload, resolve_at) VALUES (?, ?, ?, ?)",
                (scholar_id, kind, json.dumps(payload), resolve_at.isoformat()),
            )
            conn.commit()

    def due_followups(self, now: datetime) -> List[Tuple[int, str, str, Dict[str, object]]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT id, scholar_id, kind, payload FROM followups WHERE resolve_at <= ? ORDER BY id ASC",
                (now.isoformat(),),
            ).fetchall()
        return [
            (
                row[0],
                row[1],
                row[2],
                json.loads(row[3]),
            )
            for row in rows
        ]

    def clear_followup(self, followup_id: int) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("DELETE FROM followups WHERE id = ?", (followup_id,))
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

    # Theory log --------------------------------------------------------
    def record_theory(self, record: TheoryRecord) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO theories (timestamp, player_id, theory, confidence, supporters, deadline)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.timestamp.isoformat(),
                    record.player_id,
                    record.theory,
                    record.confidence,
                    json.dumps(record.supporters),
                    record.deadline,
                ),
            )
            conn.commit()

    # Expedition log ----------------------------------------------------
    def record_expedition(self, record: ExpeditionRecord, result_payload: Dict[str, object] | None = None) -> None:
        payload_json = json.dumps(result_payload or {})
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "REPLACE INTO expeditions (code, timestamp, player_id, expedition_type, objective, team, funding, prep_depth, confidence, outcome, reputation_delta, result_payload)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.code,
                    record.timestamp.isoformat(),
                    record.player_id,
                    record.expedition_type,
                    record.objective,
                    json.dumps(record.team),
                    json.dumps(record.funding),
                    record.prep_depth,
                    record.confidence,
                    record.outcome,
                    record.reputation_delta,
                    payload_json,
                ),
            )
            conn.commit()

    # Press archive -----------------------------------------------------
    def record_press_release(self, record: PressRecord) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO press_releases (timestamp, type, headline, body, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    record.timestamp.isoformat(),
                    record.release.type,
                    record.release.headline,
                    record.release.body,
                    json.dumps(record.release.metadata),
                ),
            )
            conn.commit()

    def list_press_releases(self, limit: int | None = None, offset: int = 0) -> List[PressRecord]:
        records: List[PressRecord] = []
        query = "SELECT timestamp, type, headline, body, metadata FROM press_releases ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = (limit, offset)
        else:
            params = ()
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(query, params).fetchall()
        for ts, type_, headline, body, metadata in rows:
            release = PressRelease(type=type_, headline=headline, body=body, metadata=json.loads(metadata))
            records.append(PressRecord(timestamp=datetime.fromisoformat(ts), release=release))
        return records


__all__ = ["GameState"]
