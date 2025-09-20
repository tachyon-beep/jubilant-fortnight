"""Game state management and persistence."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    Event,
    ExpeditionRecord,
    OfferRecord,
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
CREATE TABLE IF NOT EXISTS timeline (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    current_year INTEGER NOT NULL,
    last_advanced TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentorships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    scholar_id TEXT NOT NULL,
    start_date TEXT NOT NULL,
    status TEXT NOT NULL,
    career_track TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS conferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    timestamp TEXT NOT NULL,
    player_id TEXT NOT NULL,
    theory_id INTEGER NOT NULL,
    confidence TEXT NOT NULL,
    supporters TEXT NOT NULL,
    opposition TEXT NOT NULL,
    outcome TEXT,
    reputation_delta INTEGER NOT NULL DEFAULT 0,
    result_payload TEXT,
    FOREIGN KEY (theory_id) REFERENCES theories (id)
);
CREATE TABLE IF NOT EXISTS symposium_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    selected_topic_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expire_at TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (selected_topic_id) REFERENCES symposium_topics (id)
);
CREATE INDEX IF NOT EXISTS idx_symposium_proposals_status
    ON symposium_proposals (status, created_at);
CREATE INDEX IF NOT EXISTS idx_symposium_proposals_expire
    ON symposium_proposals (status, expire_at);
CREATE TABLE IF NOT EXISTS symposium_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symposium_date TEXT NOT NULL,
    topic TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'voting',
    winner TEXT,
    created_at TEXT NOT NULL,
    proposal_id INTEGER,
    FOREIGN KEY (proposal_id) REFERENCES symposium_proposals (id)
);
CREATE TABLE IF NOT EXISTS symposium_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    vote_option INTEGER NOT NULL,
    voted_at TEXT NOT NULL,
    FOREIGN KEY (topic_id) REFERENCES symposium_topics (id),
    UNIQUE (topic_id, player_id)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_type TEXT NOT NULL,
    actor_id TEXT,
    subject_id TEXT,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    scheduled_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_table TEXT,
    source_id TEXT,
    result TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status_scheduled
    ON orders (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_orders_type_status
    ON orders (order_type, status);
CREATE TABLE IF NOT EXISTS symposium_pledges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    pledge_amount INTEGER NOT NULL,
    faction TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (topic_id) REFERENCES symposium_topics (id)
);
CREATE INDEX IF NOT EXISTS idx_symposium_pledges_topic_status
    ON symposium_pledges (topic_id, status);
CREATE TABLE IF NOT EXISTS symposium_participation (
    player_id TEXT PRIMARY KEY,
    miss_streak INTEGER NOT NULL DEFAULT 0,
    grace_window_start TEXT,
    grace_miss_consumed INTEGER NOT NULL DEFAULT 0,
    last_voted_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS symposium_debts (
    player_id TEXT NOT NULL,
    faction TEXT NOT NULL,
    amount INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reprisal_level INTEGER NOT NULL DEFAULT 0,
    last_reprisal_at TEXT,
    PRIMARY KEY (player_id, faction)
);
CREATE TABLE IF NOT EXISTS queued_press (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class GameState:
    """High level interface for working with persistent state."""

    def __init__(
        self,
        db_path: Path,
        repository: ScholarRepository | None = None,
        *,
        start_year: int,
    ) -> None:
        self._db_path = db_path
        self._repo = repository or ScholarRepository()
        self._start_year = start_year
        self._ensure_schema()
        self._ensure_timeline()
        self._cached_players: Dict[str, Player] = {}
        self._cached_scholars: Dict[str, Scholar] = {}

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.executescript(_DB_SCHEMA)
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info('symposium_proposals')").fetchall()
            }
            if "expire_at" not in columns:
                conn.execute("ALTER TABLE symposium_proposals ADD COLUMN expire_at TEXT")
            if "priority" not in columns:
                conn.execute(
                    "ALTER TABLE symposium_proposals ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
                )
            debt_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info('symposium_debts')").fetchall()
            }
            if "reprisal_level" not in debt_columns:
                conn.execute(
                    "ALTER TABLE symposium_debts ADD COLUMN reprisal_level INTEGER NOT NULL DEFAULT 0"
                )
            if "last_reprisal_at" not in debt_columns:
                conn.execute(
                    "ALTER TABLE symposium_debts ADD COLUMN last_reprisal_at TEXT"
                )
            conn.commit()

    def _ensure_timeline(self) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT current_year, last_advanced FROM timeline WHERE singleton = 1"
            ).fetchone()
            if row is None:
                now = datetime.now(timezone.utc)
                conn.execute(
                    "INSERT INTO timeline (singleton, current_year, last_advanced) VALUES (1, ?, ?)",
                    (self._start_year, now.isoformat()),
                )
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
            try:
                influence = json.loads(row[3])
                cooldowns = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                # Skip rows with malformed JSON data
                continue
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

    def list_followups(self) -> List[Tuple[int, str, str, datetime, Dict[str, object]]]:
        """List all followups (not just due ones)."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT id, scholar_id, kind, resolve_at, payload
                FROM followups ORDER BY resolve_at ASC"""
            ).fetchall()
        return [
            (row[0], row[1], row[2], datetime.fromisoformat(row[3]), json.loads(row[4]))
            for row in rows
        ]

    # Scheduled press --------------------------------------------------
    def enqueue_press_release(
        self,
        release: PressRelease,
        release_at: datetime,
    ) -> None:
        payload = json.dumps(
            {
                "type": release.type,
                "headline": release.headline,
                "body": release.body,
                "metadata": release.metadata,
            }
        )
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO queued_press (release_at, payload) VALUES (?, ?)",
                (release_at.isoformat(), payload),
            )
            conn.commit()

    def due_queued_press(self, now: datetime) -> List[Tuple[int, datetime, Dict[str, object]]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT id, release_at, payload FROM queued_press WHERE release_at <= ? ORDER BY release_at ASC",
                (now.isoformat(),),
            ).fetchall()
        releases: List[Tuple[int, datetime, Dict[str, object]]] = []
        for row in rows:
            queue_id = int(row[0])
            release_at = datetime.fromisoformat(row[1])
            payload = json.loads(row[2])
            releases.append((queue_id, release_at, payload))
        return releases

    def count_queued_press(self) -> int:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM queued_press").fetchone()
        return int(row[0]) if row else 0

    def clear_queued_press(self, queue_id: int) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("DELETE FROM queued_press WHERE id = ?", (queue_id,))
            conn.commit()

    def list_queued_press(self) -> List[Tuple[int, datetime, Dict[str, object]]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT id, release_at, payload FROM queued_press ORDER BY release_at ASC"
            ).fetchall()
        return [
            (int(row[0]), datetime.fromisoformat(row[1]), json.loads(row[2]))
            for row in rows
        ]

    # Generic orders ---------------------------------------------------
    def enqueue_order(
        self,
        order_type: str,
        *,
        payload: Dict[str, object],
        actor_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        source_table: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        scheduled_iso = scheduled_at.isoformat() if scheduled_at else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO orders
                       (order_type, actor_id, subject_id, payload, status, scheduled_at, created_at, updated_at, source_table, source_id, result)
                       VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, NULL)""",
                (
                    order_type,
                    actor_id,
                    subject_id,
                    json.dumps(payload),
                    scheduled_iso,
                    now,
                    now,
                    source_table,
                    source_id,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def fetch_due_orders(
        self,
        order_type: str,
        now: datetime,
    ) -> List[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT id, actor_id, subject_id, payload, scheduled_at
                       FROM orders
                       WHERE order_type = ?
                         AND status = 'pending'
                         AND (scheduled_at IS NULL OR scheduled_at <= ?)
                       ORDER BY created_at""",
                (order_type, now.isoformat()),
            ).fetchall()
        due_orders: List[Dict[str, object]] = []
        for row in rows:
            scheduled_at = datetime.fromisoformat(row[4]) if row[4] else None
            due_orders.append(
                {
                    "id": int(row[0]),
                    "actor_id": row[1],
                    "subject_id": row[2],
                    "payload": json.loads(row[3]),
                    "scheduled_at": scheduled_at,
                }
            )
        return due_orders

    def update_order_status(
        self,
        order_id: int,
        status: str,
        *,
        result: Optional[Dict[str, object]] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE orders
                       SET status = ?, updated_at = ?, result = ?
                       WHERE id = ?""",
                (
                    status,
                    now,
                    json.dumps(result) if result is not None else None,
                    order_id,
                ),
            )
            conn.commit()

    def list_orders(
        self,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        query = "SELECT id, order_type, actor_id, subject_id, payload, status, scheduled_at, created_at, updated_at, source_table, source_id, result FROM orders"
        conditions: List[str] = []
        params: List[object] = []
        if order_type:
            conditions.append("order_type = ?")
            params.append(order_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at"

        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(query, params).fetchall()

        orders: List[Dict[str, object]] = []
        for row in rows:
            scheduled_at = datetime.fromisoformat(row[6]) if row[6] else None
            orders.append(
                {
                    "id": int(row[0]),
                    "order_type": row[1],
                    "actor_id": row[2],
                    "subject_id": row[3],
                    "payload": json.loads(row[4]),
                    "status": row[5],
                    "scheduled_at": scheduled_at,
                    "created_at": datetime.fromisoformat(row[7]),
                    "updated_at": datetime.fromisoformat(row[8]),
                    "source_table": row[9],
                    "source_id": row[10],
                    "result": json.loads(row[11]) if row[11] else None,
                }
            )
        return orders

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

    # Timeline ----------------------------------------------------------
    def current_year(self) -> int:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT current_year FROM timeline WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return self._start_year
        return int(row[0])

    def advance_timeline(self, now: datetime, days_per_year: int) -> Tuple[int, int]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT current_year, last_advanced FROM timeline WHERE singleton = 1"
            ).fetchone()
        if row is None:
            # Should not happen, but keep behaviour predictable
            current_year = self._start_year
            last_advanced = now
        else:
            current_year = int(row[0])
            last_advanced = datetime.fromisoformat(row[1])
        delta_days = (now.date() - last_advanced.date()).days
        if delta_days < days_per_year:
            return 0, current_year
        years_elapsed = delta_days // days_per_year
        new_year = current_year + years_elapsed
        new_anchor = last_advanced + timedelta(days=years_elapsed * days_per_year)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "UPDATE timeline SET current_year = ?, last_advanced = ? WHERE singleton = 1",
                (new_year, new_anchor.isoformat()),
            )
            conn.commit()
        return years_elapsed, new_year

    # Theory log --------------------------------------------------------
    def record_theory(self, record: TheoryRecord) -> int:
        """Record a theory and return its ID."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
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
            return cursor.lastrowid

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
            # Also record as an event for audit trail
            event_payload = {
                "code": record.code,
                "player_id": record.player_id,
                "expedition_type": record.expedition_type,
                "objective": record.objective,
                "team": record.team,
                "funding": record.funding,
            }
            conn.execute(
                "INSERT INTO events (timestamp, action, payload) VALUES (?, ?, ?)",
                (record.timestamp.isoformat(), "expedition_queued", json.dumps(event_payload))
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

    # Offer management (Defection negotiations) ------------------------
    def save_offer(self, offer: OfferRecord) -> int:
        """Save a defection offer to the database. First actual use of offers table!"""
        with closing(sqlite3.connect(self._db_path)) as conn:
            # Convert influence_offered and terms to JSON
            payload = {
                "rival_id": offer.rival_id,
                "patron_id": offer.patron_id,
                "offer_type": offer.offer_type,
                "influence_offered": offer.influence_offered,
                "terms": offer.terms,
                "parent_offer_id": offer.parent_offer_id,
                "resolved_at": offer.resolved_at.isoformat() if offer.resolved_at else None,
            }

            cursor = conn.execute(
                """INSERT INTO offers (scholar_id, faction, payload, status, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    offer.scholar_id,
                    offer.faction,
                    json.dumps(payload),
                    offer.status,
                    offer.created_at.isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_offer(self, offer_id: int) -> Optional[OfferRecord]:
        """Retrieve a specific offer by ID."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT id, scholar_id, faction, payload, status, created_at FROM offers WHERE id = ?",
                (offer_id,),
            ).fetchone()

            if not row:
                return None

            id_, scholar_id, faction, payload_json, status, created_at = row
            payload = json.loads(payload_json)

            return OfferRecord(
                id=id_,
                scholar_id=scholar_id,
                faction=faction,
                rival_id=payload.get("rival_id", ""),
                patron_id=payload.get("patron_id", ""),
                offer_type=payload.get("offer_type", "initial"),
                influence_offered=payload.get("influence_offered", {}),
                terms=payload.get("terms", {}),
                status=status,
                parent_offer_id=payload.get("parent_offer_id"),
                created_at=datetime.fromisoformat(created_at),
                resolved_at=datetime.fromisoformat(payload["resolved_at"]) if payload.get("resolved_at") else None,
            )

    def list_active_offers(self, player_id: Optional[str] = None) -> List[OfferRecord]:
        """Get all pending offers, optionally filtered by player involvement."""
        query = "SELECT id, scholar_id, faction, payload, status, created_at FROM offers WHERE status IN ('pending', 'countered')"
        params = []

        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(query, params).fetchall()

        offers = []
        for id_, scholar_id, faction, payload_json, status, created_at in rows:
            payload = json.loads(payload_json)

            # Filter by player if specified
            if player_id and player_id not in [payload.get("rival_id"), payload.get("patron_id")]:
                continue

            offers.append(OfferRecord(
                id=id_,
                scholar_id=scholar_id,
                faction=faction,
                rival_id=payload.get("rival_id", ""),
                patron_id=payload.get("patron_id", ""),
                offer_type=payload.get("offer_type", "initial"),
                influence_offered=payload.get("influence_offered", {}),
                terms=payload.get("terms", {}),
                status=status,
                parent_offer_id=payload.get("parent_offer_id"),
                created_at=datetime.fromisoformat(created_at),
                resolved_at=datetime.fromisoformat(payload["resolved_at"]) if payload.get("resolved_at") else None,
            ))

        return offers

    def update_offer_status(self, offer_id: int, new_status: str, resolved_at: Optional[datetime] = None) -> None:
        """Update the status of an offer."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            # First get the current offer to update its payload
            row = conn.execute(
                "SELECT payload FROM offers WHERE id = ?",
                (offer_id,),
            ).fetchone()

            if row:
                payload = json.loads(row[0])
                if resolved_at:
                    payload["resolved_at"] = resolved_at.isoformat()

                conn.execute(
                    "UPDATE offers SET status = ?, payload = ? WHERE id = ?",
                    (new_status, json.dumps(payload), offer_id),
                )
                conn.commit()

    def get_offer_chain(self, offer_id: int) -> List[OfferRecord]:
        """Get all offers in a negotiation chain."""
        offers = []
        current_offer = self.get_offer(offer_id)

        if not current_offer:
            return offers

        # Find the root offer
        while current_offer.parent_offer_id:
            parent = self.get_offer(current_offer.parent_offer_id)
            if parent:
                current_offer = parent
            else:
                break

        # Now collect all offers in the chain
        def collect_children(offer: OfferRecord) -> None:
            offers.append(offer)
            # Find all offers that have this as parent
            with closing(sqlite3.connect(self._db_path)) as conn:
                rows = conn.execute(
                    "SELECT id FROM offers WHERE payload LIKE ?",
                    (f'%"parent_offer_id": {offer.id}%',),
                ).fetchall()

                for (child_id,) in rows:
                    child = self.get_offer(child_id)
                    if child:
                        collect_children(child)

        collect_children(current_offer)
        return offers

    # Mentorship management ---------------------------------------------
    def add_mentorship(
        self,
        player_id: str,
        scholar_id: str,
        career_track: str | None = None,
        created_at: datetime | None = None,
    ) -> int:
        """Add a new mentorship relationship."""
        now = created_at or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO mentorships
                   (player_id, scholar_id, start_date, status, career_track, created_at, resolved_at)
                   VALUES (?, ?, ?, 'pending', ?, ?, NULL)""",
                (
                    player_id,
                    scholar_id,
                    now.isoformat(),
                    career_track,
                    now.isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_active_mentorship(self, scholar_id: str) -> Optional[Tuple[int, str, str, str]]:
        """Get active mentorship for a scholar if it exists."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, player_id, career_track, start_date
                   FROM mentorships
                   WHERE scholar_id = ? AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1""",
                (scholar_id,),
            ).fetchone()
            return row if row else None

    def get_pending_mentorships(self) -> List[Tuple[int, str, str, str | None]]:
        """Get all pending mentorships for resolution."""
        orders = self.list_orders(order_type="mentorship_activation", status="pending")
        pending: List[Tuple[int, str, str, str | None]] = []
        for order in orders:
            payload = order["payload"]
            mentorship_id = payload.get("mentorship_id")
            if mentorship_id is None:
                continue
            pending.append(
                (
                    mentorship_id,
                    order.get("actor_id"),
                    payload.get("scholar_id"),
                    payload.get("career_track"),
                )
            )
        return pending

    def get_mentorship_by_id(
        self,
        mentorship_id: int,
    ) -> Optional[Tuple[int, str, str, str | None, str]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, player_id, scholar_id, career_track, status
                   FROM mentorships
                   WHERE id = ?""",
                (mentorship_id,),
            ).fetchone()
        if not row:
            return None
        return row[0], row[1], row[2], row[3], row[4]

    def activate_mentorship(self, mentorship_id: int) -> None:
        """Mark a mentorship as active."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "UPDATE mentorships SET status = 'active' WHERE id = ?",
                (mentorship_id,),
            )
            conn.commit()

    def complete_mentorship(self, mentorship_id: int, resolved_at: datetime | None = None) -> None:
        """Mark a mentorship as completed."""
        now = resolved_at or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                "UPDATE mentorships SET status = 'completed', resolved_at = ? WHERE id = ?",
                (now.isoformat(), mentorship_id),
            )
            conn.commit()

    # Conference management ---------------------------------------------
    def add_conference(
        self,
        code: str,
        player_id: str,
        theory_id: int,
        confidence: str,
        supporters: List[str],
        opposition: List[str],
        timestamp: datetime | None = None,
    ) -> None:
        """Queue a conference for resolution."""
        now = timestamp or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO conferences
                   (code, timestamp, player_id, theory_id, confidence, supporters, opposition)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    code,
                    now.isoformat(),
                    player_id,
                    theory_id,
                    confidence,
                    json.dumps(supporters),
                    json.dumps(opposition),
                ),
            )
            conn.commit()

    def get_pending_conferences(self) -> List[Tuple[str, str, int, str, List[str], List[str]]]:
        """Get conferences awaiting resolution."""
        orders = self.list_orders(order_type="conference_resolution", status="pending")
        pending: List[Tuple[str, str, int, str, List[str], List[str]]] = []
        for order in orders:
            payload = order["payload"]
            code = payload.get("conference_code") or order.get("subject_id")
            if not code:
                continue
            player_id = order.get("actor_id")
            theory_id = payload.get("theory_id")
            confidence = payload.get("confidence")
            supporters = payload.get("supporters", [])
            opposition = payload.get("opposition", [])
            pending.append(
                (
                    code,
                    player_id,
                    theory_id,
                    confidence,
                    supporters,
                    opposition,
                )
            )
        return pending

    def get_conference_by_code(
        self,
        code: str,
    ) -> Optional[Tuple[str, str, int, str, List[str], List[str], datetime]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT code, player_id, theory_id, confidence, supporters, opposition, timestamp
                   FROM conferences
                   WHERE code = ?""",
                (code,),
            ).fetchone()
        if not row:
            return None
        return (
            row[0],
            row[1],
            int(row[2]),
            row[3],
            json.loads(row[4]),
            json.loads(row[5]),
            datetime.fromisoformat(row[6]),
        )

    def resolve_conference(
        self,
        code: str,
        outcome: str,
        reputation_delta: int,
        result_payload: Dict[str, object] | None = None,
    ) -> None:
        """Mark a conference as resolved with outcome."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE conferences
                   SET outcome = ?, reputation_delta = ?, result_payload = ?
                   WHERE code = ?""",
                (
                    outcome,
                    reputation_delta,
                    json.dumps(result_payload) if result_payload else None,
                    code,
                ),
            )
            conn.commit()

    def get_theory_by_id(self, theory_id: int) -> Optional[Tuple[int, TheoryRecord]]:
        """Retrieve a theory by ID, returning (id, record) tuple."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, timestamp, player_id, theory, confidence, supporters, deadline
                   FROM theories WHERE id = ?""",
                (theory_id,),
            ).fetchone()
            if row:
                record = TheoryRecord(
                    timestamp=datetime.fromisoformat(row[1]),
                    player_id=row[2],
                    theory=row[3],
                    confidence=row[4],
                    supporters=json.loads(row[5]),
                    deadline=row[6],
                )
                return row[0], record
            return None

    def get_last_theory_id_by_player(self, player_id: str) -> Optional[int]:
        """Get the ID of the most recent theory submitted by a player."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id FROM theories
                   WHERE player_id = ?
                   ORDER BY id DESC
                   LIMIT 1""",
                (player_id,),
            ).fetchone()
            return row[0] if row else None

    def pending_theories(self) -> List[Tuple[int, TheoryRecord]]:
        """Get all theories with deadlines that haven't passed yet."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            rows = conn.execute(
                """
                SELECT id, player_id, theory, confidence, supporters, timestamp, deadline
                FROM theories
                WHERE deadline >= ?
                ORDER BY deadline ASC
                """,
                (current_date,)
            ).fetchall()

        return [
            (
                row[0],
                TheoryRecord(
                    player_id=row[1],
                    theory=row[2],
                    confidence=row[3],
                    supporters=json.loads(row[4]) if row[4] else [],
                    timestamp=datetime.fromisoformat(row[5]),
                    deadline=row[6]
                )
            )
            for row in rows
        ]

    def list_theories(self, limit: int | None = None) -> List[Tuple[int, TheoryRecord]]:
        """List all theories with their IDs, optionally limited."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            query = "SELECT id, timestamp, player_id, theory, confidence, supporters, deadline FROM theories ORDER BY id DESC"
            if limit is not None:
                query += f" LIMIT {limit}"
            rows = conn.execute(query).fetchall()
            theories = []
            for row in rows:
                record = TheoryRecord(
                    timestamp=datetime.fromisoformat(row[1]),
                    player_id=row[2],
                    theory=row[3],
                    confidence=row[4],
                    supporters=json.loads(row[5]),
                    deadline=row[6],
                )
                theories.append((row[0], record))
            return theories

    # Symposium management ----------------------------------------------
    def create_symposium_topic(
        self,
        symposium_date: datetime,
        topic: str,
        description: str,
        *,
        proposal_id: int | None = None,
        created_at: datetime | None = None,
    ) -> int:
        """Create a new symposium topic for voting."""
        now = created_at or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO symposium_topics
                   (symposium_date, topic, description, status, created_at, proposal_id)
                   VALUES (?, ?, ?, 'voting', ?, ?)""",
                (
                    symposium_date.isoformat(),
                    topic,
                    description,
                    now.isoformat(),
                    proposal_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_current_symposium_topic(self) -> Optional[Tuple[int, str, str, int | None, List[int]]]:
        """Get the current symposium topic if in voting phase.

        Returns: (topic_id, topic, description, proposal_id, list of vote options) or None
        """
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, topic, description, proposal_id
                   FROM symposium_topics
                   WHERE status = 'voting'
                   ORDER BY created_at DESC
                   LIMIT 1""",
            ).fetchone()
            if row:
                # Generate 3 voting options
                return (row[0], row[1], row[2], row[3], [1, 2, 3])
            return None

    def record_symposium_vote(
        self,
        topic_id: int,
        player_id: str,
        vote_option: int,
        voted_at: datetime | None = None,
    ) -> None:
        """Record a player's vote on a symposium topic."""
        now = voted_at or datetime.now(timezone.utc)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO symposium_votes
                   (topic_id, player_id, vote_option, voted_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    topic_id,
                    player_id,
                    vote_option,
                    now.isoformat(),
                ),
            )
            conn.commit()

    def get_symposium_votes(self, topic_id: int) -> Dict[int, int]:
        """Get vote counts for a symposium topic.

        Returns: Dict mapping vote option to count
        """
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT vote_option, COUNT(*) as count
                   FROM symposium_votes
                   WHERE topic_id = ?
                   GROUP BY vote_option""",
                (topic_id,),
            ).fetchall()
        return {option: count for option, count in rows}

    def list_symposium_voters(self, topic_id: int) -> List[str]:
        """Return the player ids that have voted for the symposium."""

        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                "SELECT player_id FROM symposium_votes WHERE topic_id = ?",
                (topic_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def get_symposium_topic(self, topic_id: int) -> Optional[Dict[str, object]]:
        """Return metadata for the requested symposium topic."""

        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, symposium_date, topic, description, status, winner, created_at, proposal_id
                   FROM symposium_topics
                   WHERE id = ?""",
                (topic_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "symposium_date": datetime.fromisoformat(row[1]) if row[1] else None,
            "topic": row[2],
            "description": row[3],
            "status": row[4],
            "winner": row[5],
            "created_at": datetime.fromisoformat(row[6]) if row[6] else None,
            "proposal_id": row[7],
        }

    def has_symposium_vote(self, topic_id: int, player_id: str) -> bool:
        """Return True if the player has already voted on the topic."""

        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM symposium_votes WHERE topic_id = ? AND player_id = ?",
                (topic_id, player_id),
            ).fetchone()
        return row is not None

    # Symposium proposals ----------------------------------------------
    def submit_symposium_proposal(
        self,
        *,
        player_id: str,
        topic: str,
        description: str,
        created_at: datetime | None = None,
        expire_at: datetime | None = None,
        priority: int = 0,
    ) -> int:
        now = created_at or datetime.now(timezone.utc)
        expire_iso = expire_at.isoformat() if expire_at else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO symposium_proposals
                   (player_id, topic, description, status, created_at, updated_at, expire_at, priority)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
                (
                    player_id,
                    topic,
                    description,
                    now.isoformat(),
                    now.isoformat(),
                    expire_iso,
                    priority,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def count_pending_symposium_proposals(
        self,
        now: datetime | None = None,
    ) -> int:
        clause = "status = 'pending'"
        params: List[object] = []
        if now is not None:
            clause += " AND (expire_at IS NULL OR expire_at > ?)"
            params.append(now.isoformat())
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM symposium_proposals WHERE {clause}",
                params,
            ).fetchone()
        return int(row[0]) if row else 0

    def count_player_pending_symposium_proposals(
        self,
        player_id: str,
        *,
        now: datetime | None = None,
    ) -> int:
        clause = "status = 'pending' AND player_id = ?"
        params: List[object] = [player_id]
        if now is not None:
            clause += " AND (expire_at IS NULL OR expire_at > ?)"
            params.append(now.isoformat())
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM symposium_proposals WHERE {clause}",
                params,
            ).fetchone()
        return int(row[0]) if row else 0

    def expire_symposium_proposals(self, cutoff: datetime) -> List[int]:
        cutoff_iso = cutoff.isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT id FROM symposium_proposals
                       WHERE status = 'pending' AND expire_at IS NOT NULL AND expire_at <= ?""",
                (cutoff_iso,),
            ).fetchall()
            expired_ids = [int(row[0]) for row in rows]
            if expired_ids:
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.executemany(
                    """UPDATE symposium_proposals
                           SET status = 'expired', updated_at = ?
                           WHERE id = ?""",
                    [(now_iso, proposal_id) for proposal_id in expired_ids],
                )
                conn.commit()
        return expired_ids

    def list_pending_symposium_proposals(
        self,
        *,
        limit: int | None = None,
        now: datetime | None = None,
    ) -> List[Dict[str, object]]:
        sql = (
            "SELECT id, player_id, topic, description, status, created_at, updated_at, expire_at, priority "
            "FROM symposium_proposals WHERE status = 'pending'"
        )
        params: List[object] = []
        if now is not None:
            sql += " AND (expire_at IS NULL OR expire_at > ?)"
            params.append(now.isoformat())
        sql += " ORDER BY priority DESC, created_at"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()
        proposals: List[Dict[str, object]] = []
        for row in rows:
            proposals.append(
                {
                    "id": row[0],
                    "player_id": row[1],
                    "topic": row[2],
                    "description": row[3],
                    "status": row[4],
                    "created_at": datetime.fromisoformat(row[5]) if row[5] else None,
                    "updated_at": datetime.fromisoformat(row[6]) if row[6] else None,
                    "expire_at": datetime.fromisoformat(row[7]) if row[7] else None,
                    "priority": row[8],
                }
            )
        return proposals

    def fetch_next_symposium_proposal(
        self,
        now: datetime | None = None,
    ) -> Optional[Dict[str, object]]:
        proposals = self.list_pending_symposium_proposals(limit=1, now=now)
        return proposals[0] if proposals else None

    def get_symposium_proposal(self, proposal_id: int) -> Optional[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, player_id, topic, description, status, created_at, updated_at, selected_topic_id, expire_at, priority
                   FROM symposium_proposals
                   WHERE id = ?""",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "player_id": row[1],
            "topic": row[2],
            "description": row[3],
            "status": row[4],
            "created_at": datetime.fromisoformat(row[5]) if row[5] else None,
            "updated_at": datetime.fromisoformat(row[6]) if row[6] else None,
            "selected_topic_id": row[7],
            "expire_at": datetime.fromisoformat(row[8]) if row[8] else None,
            "priority": row[9],
        }

    def update_symposium_proposal_status(
        self,
        proposal_id: int,
        *,
        status: str,
        selected_topic_id: int | None = None,
        expire_at: datetime | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        expire_iso = expire_at.isoformat() if expire_at else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE symposium_proposals
                   SET status = ?,
                       selected_topic_id = COALESCE(?, selected_topic_id),
                       expire_at = COALESCE(?, expire_at),
                       updated_at = ?
                   WHERE id = ?""",
                (status, selected_topic_id, expire_iso, now, proposal_id),
            )
            conn.commit()

    # Symposium pledges & participation --------------------------------

    def list_recent_symposium_topics(
        self,
        *,
        limit: int,
    ) -> List[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT id, symposium_date, topic, description, proposal_id, status, winner, created_at
                       FROM symposium_topics
                       ORDER BY created_at DESC
                       LIMIT ?""",
                (limit,),
            ).fetchall()
        topics: List[Dict[str, object]] = []
        for row in rows:
            topics.append(
                {
                    "id": row[0],
                    "symposium_date": datetime.fromisoformat(row[1]) if row[1] else None,
                    "topic": row[2],
                    "description": row[3],
                    "proposal_id": row[4],
                    "status": row[5],
                    "winner": row[6],
                    "created_at": datetime.fromisoformat(row[7]) if row[7] else None,
                }
            )
        return topics

    def record_symposium_pledge(
        self,
        *,
        topic_id: int,
        player_id: str,
        pledge_amount: int,
        faction: Optional[str],
        created_at: Optional[datetime] = None,
    ) -> int:
        now = (created_at or datetime.now(timezone.utc)).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            cursor = conn.execute(
                """INSERT INTO symposium_pledges
                       (topic_id, player_id, pledge_amount, faction, status, created_at)
                       VALUES (?, ?, ?, ?, 'pending', ?)""",
                (topic_id, player_id, pledge_amount, faction, now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def update_symposium_pledge_status(
        self,
        *,
        topic_id: int,
        player_id: str,
        status: str,
        resolved_at: Optional[datetime] = None,
        pledge_amount: Optional[int] = None,
        faction: Optional[str] = None,
    ) -> None:
        now_iso = (resolved_at or datetime.now(timezone.utc)).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE symposium_pledges
                       SET status = ?,
                           resolved_at = ?,
                           pledge_amount = COALESCE(?, pledge_amount),
                           faction = COALESCE(?, faction)
                       WHERE topic_id = ? AND player_id = ?""",
                (status, now_iso, pledge_amount, faction, topic_id, player_id),
            )
            conn.commit()

    def list_symposium_pledges(
        self,
        *,
        topic_id: int,
        status: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        sql = (
            "SELECT id, player_id, pledge_amount, faction, status, created_at, resolved_at "
            "FROM symposium_pledges WHERE topic_id = ?"
        )
        params: List[object] = [topic_id]
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()
        pledges: List[Dict[str, object]] = []
        for row in rows:
            pledges.append(
                {
                    "id": row[0],
                    "player_id": row[1],
                    "pledge_amount": row[2],
                    "faction": row[3],
                    "status": row[4],
                    "created_at": datetime.fromisoformat(row[5]) if row[5] else None,
                    "resolved_at": datetime.fromisoformat(row[6]) if row[6] else None,
                }
            )
        return pledges

    def get_symposium_pledge(
        self,
        *,
        topic_id: int,
        player_id: str,
    ) -> Optional[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT id, pledge_amount, faction, status, created_at, resolved_at
                       FROM symposium_pledges
                       WHERE topic_id = ? AND player_id = ?""",
                (topic_id, player_id),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "pledge_amount": row[1],
            "faction": row[2],
            "status": row[3],
            "created_at": datetime.fromisoformat(row[4]) if row[4] else None,
            "resolved_at": datetime.fromisoformat(row[5]) if row[5] else None,
        }

    def list_recent_symposium_pledges_for_player(
        self,
        player_id: str,
        *,
        limit: int = 5,
    ) -> List[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT p.topic_id, t.topic, t.symposium_date, p.pledge_amount, p.faction,
                              p.status, p.created_at, p.resolved_at
                       FROM symposium_pledges AS p
                       LEFT JOIN symposium_topics AS t ON p.topic_id = t.id
                       WHERE p.player_id = ?
                       ORDER BY p.created_at DESC
                       LIMIT ?""",
                (player_id, limit),
            ).fetchall()
        pledges: List[Dict[str, object]] = []
        for row in rows:
            pledges.append(
                {
                    "topic_id": row[0],
                    "topic": row[1],
                    "symposium_date": datetime.fromisoformat(row[2]) if row[2] else None,
                    "pledge_amount": row[3],
                    "faction": row[4],
                    "status": row[5],
                    "created_at": datetime.fromisoformat(row[6]) if row[6] else None,
                    "resolved_at": datetime.fromisoformat(row[7]) if row[7] else None,
                }
            )
        return pledges

    def list_symposium_debts(
        self,
        player_id: str,
    ) -> List[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(
                """SELECT faction, amount, created_at, updated_at, reprisal_level, last_reprisal_at
                       FROM symposium_debts WHERE player_id = ?""",
                (player_id,),
            ).fetchall()
        debts: List[Dict[str, object]] = []
        for row in rows:
            debts.append(
                {
                    "player_id": player_id,
                    "faction": row[0],
                    "amount": int(row[1]),
                    "created_at": datetime.fromisoformat(row[2]) if row[2] else None,
                    "updated_at": datetime.fromisoformat(row[3]) if row[3] else None,
                    "reprisal_level": int(row[4]) if row[4] is not None else 0,
                    "last_reprisal_at": datetime.fromisoformat(row[5]) if row[5] else None,
                }
            )
        return debts

    def record_symposium_debt(
        self,
        *,
        player_id: str,
        faction: str,
        amount: int,
        now: Optional[datetime] = None,
    ) -> None:
        if amount <= 0:
            return
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO symposium_debts (player_id, faction, amount, created_at, updated_at, reprisal_level, last_reprisal_at)
                       VALUES (?, ?, ?, ?, ?, 0, NULL)
                       ON CONFLICT(player_id, faction) DO UPDATE SET
                           amount = symposium_debts.amount + excluded.amount,
                           updated_at = excluded.updated_at""",
                (player_id, faction, amount, timestamp, timestamp),
            )
            conn.commit()

    def apply_symposium_debt_payment(
        self,
        *,
        player_id: str,
        faction: str,
        amount: int,
        now: Optional[datetime] = None,
    ) -> int:
        if amount <= 0:
            return 0
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT amount FROM symposium_debts WHERE player_id = ? AND faction = ?",
                (player_id, faction),
            ).fetchone()
            if not row:
                return 0
            current = int(row[0])
            paid = min(current, amount)
            remaining = current - paid
            if remaining == 0:
                conn.execute(
                    "DELETE FROM symposium_debts WHERE player_id = ? AND faction = ?",
                    (player_id, faction),
                )
            else:
                conn.execute(
                    """UPDATE symposium_debts
                           SET amount = ?, updated_at = ?
                           WHERE player_id = ? AND faction = ?""",
                    (
                        remaining,
                        (now or datetime.now(timezone.utc)).isoformat(),
                        player_id,
                        faction,
                    ),
                )
            conn.commit()
            return paid

    def update_symposium_debt_reprisal(
        self,
        *,
        player_id: str,
        faction: str,
        reprisal_level: int,
        now: datetime,
    ) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE symposium_debts
                       SET reprisal_level = ?, last_reprisal_at = ?, updated_at = ?
                       WHERE player_id = ? AND faction = ?""",
                (
                    reprisal_level,
                    now.isoformat(),
                    now.isoformat(),
                    player_id,
                    faction,
                ),
            )
            conn.commit()

    def get_symposium_debt_record(
        self,
        *,
        player_id: str,
        faction: str,
    ) -> Optional[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT amount, created_at, updated_at, reprisal_level, last_reprisal_at
                       FROM symposium_debts
                       WHERE player_id = ? AND faction = ?""",
                (player_id, faction),
            ).fetchone()
        if not row:
            return None
        return {
            "player_id": player_id,
            "faction": faction,
            "amount": int(row[0]),
            "created_at": datetime.fromisoformat(row[1]) if row[1] else None,
            "updated_at": datetime.fromisoformat(row[2]) if row[2] else None,
            "reprisal_level": int(row[3]) if row[3] is not None else 0,
            "last_reprisal_at": datetime.fromisoformat(row[4]) if row[4] else None,
        }

    def total_symposium_debt(self, player_id: str) -> int:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT SUM(amount) FROM symposium_debts WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def get_symposium_participation(
        self,
        player_id: str,
    ) -> Optional[Dict[str, object]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                """SELECT player_id, miss_streak, grace_window_start, grace_miss_consumed, last_voted_at, updated_at
                       FROM symposium_participation
                       WHERE player_id = ?""",
                (player_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "player_id": row[0],
            "miss_streak": row[1],
            "grace_window_start": datetime.fromisoformat(row[2]) if row[2] else None,
            "grace_miss_consumed": row[3],
            "last_voted_at": datetime.fromisoformat(row[4]) if row[4] else None,
            "updated_at": datetime.fromisoformat(row[5]) if row[5] else None,
        }

    def save_symposium_participation(
        self,
        *,
        player_id: str,
        miss_streak: int,
        grace_window_start: Optional[datetime],
        grace_miss_consumed: int,
        last_voted_at: Optional[datetime],
        updated_at: Optional[datetime] = None,
    ) -> None:
        now = (updated_at or datetime.now(timezone.utc)).isoformat()
        grace_start_iso = grace_window_start.isoformat() if grace_window_start else None
        last_vote_iso = last_voted_at.isoformat() if last_voted_at else None
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO symposium_participation AS sp
                       (player_id, miss_streak, grace_window_start, grace_miss_consumed, last_voted_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(player_id) DO UPDATE SET
                           miss_streak = excluded.miss_streak,
                           grace_window_start = excluded.grace_window_start,
                           grace_miss_consumed = excluded.grace_miss_consumed,
                           last_voted_at = excluded.last_voted_at,
                           updated_at = excluded.updated_at""",
                (
                    player_id,
                    miss_streak,
                    grace_start_iso,
                    grace_miss_consumed,
                    last_vote_iso,
                    now,
                ),
            )
            conn.commit()

    def cancel_symposium_reminders(self, topic_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE orders
                   SET status = 'cancelled', updated_at = ?
                   WHERE order_type = 'symposium_vote_reminder'
                     AND subject_id = ?
                     AND status = 'pending'""",
                (now, str(topic_id)),
            )
            conn.commit()

    def complete_symposium_reminders_for_player(
        self,
        topic_id: int,
        player_id: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE orders
                   SET status = 'completed', updated_at = ?
                   WHERE order_type = 'symposium_vote_reminder'
                     AND subject_id = ?
                     AND actor_id = ?
                     AND status = 'pending'""",
                (now, str(topic_id), player_id),
            )
            conn.commit()

    def resolve_symposium_topic(
        self,
        topic_id: int,
        winner: str,
    ) -> None:
        """Mark a symposium topic as resolved with a winner."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """UPDATE symposium_topics
                   SET status = 'resolved', winner = ?
                   WHERE id = ?""",
                (winner, topic_id),
            )
            conn.commit()


__all__ = ["GameState"]
