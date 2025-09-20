"""Telemetry and success metrics tracking for The Great Work."""
from __future__ import annotations

import json
import time
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics tracked."""
    COMMAND_USAGE = "command_usage"
    FEATURE_ENGAGEMENT = "feature_engagement"
    GAME_PROGRESSION = "game_progression"
    ERROR_RATE = "error_rate"
    PERFORMANCE = "performance"
    PLAYER_ACTIVITY = "player_activity"
    SCHOLAR_STATS = "scholar_stats"
    ECONOMY_BALANCE = "economy_balance"
    LLM_ACTIVITY = "llm_activity"
    SYSTEM_EVENT = "system_event"


@dataclass
class MetricEvent:
    """Individual metric event."""
    timestamp: float
    metric_type: MetricType
    name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TelemetryCollector:
    """Collects and stores telemetry data for The Great Work."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize telemetry collector with database storage."""
        self.db_path = db_path or Path("telemetry.db")
        self._init_database()
        self._start_time = time.time()
        self._metrics_buffer: List[MetricEvent] = []
        self._flush_interval = 60  # Flush to DB every 60 seconds
        self._last_flush = time.time()

    def _init_database(self):
        """Initialize telemetry database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    metric_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    tags TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                ON metrics(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type_name
                ON metrics(metric_type, name)
            """)
            conn.commit()

    def track_command(
        self,
        command_name: str,
        player_id: str,
        guild_id: str,
        success: bool = True,
        duration_ms: Optional[float] = None,
        channel_id: Optional[str] = None,
    ):
        """Track Discord command usage."""
        tags = {
            "player_id": player_id,
            "guild_id": guild_id,
            "success": str(success),
        }
        if channel_id:
            tags["channel_id"] = channel_id

        self.record(
            MetricType.COMMAND_USAGE,
            command_name,
            1.0,
            tags=tags,
            metadata={"duration_ms": duration_ms} if duration_ms else {}
        )

    def track_feature_usage(
        self,
        feature_name: str,
        player_id: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Track feature engagement."""
        self.record(
            MetricType.FEATURE_ENGAGEMENT,
            feature_name,
            1.0,
            tags={"player_id": player_id},
            metadata=details or {}
        )

    def track_game_progression(
        self,
        event_name: str,
        value: float,
        player_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Track game progression events."""
        tags = {}
        if player_id:
            tags["player_id"] = player_id

        self.record(
            MetricType.GAME_PROGRESSION,
            event_name,
            value,
            tags=tags,
            metadata=details or {}
        )

    def track_error(
        self,
        error_type: str,
        command: Optional[str] = None,
        player_id: Optional[str] = None,
        error_details: Optional[str] = None
    ):
        """Track errors and failures."""
        tags = {}
        if command:
            tags["command"] = command
        if player_id:
            tags["player_id"] = player_id

        self.record(
            MetricType.ERROR_RATE,
            error_type,
            1.0,
            tags=tags,
            metadata={"error_details": error_details} if error_details else {}
        )

    def track_performance(
        self,
        operation: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Track performance metrics."""
        self.record(
            MetricType.PERFORMANCE,
            operation,
            duration_ms,
            tags=tags or {},
            metadata={"unit": "milliseconds"}
        )

    def track_player_activity(
        self,
        player_id: str,
        activity_type: str,
        reputation: float,
        influence_totals: Dict[str, float]
    ):
        """Track player activity and state."""
        self.record(
            MetricType.PLAYER_ACTIVITY,
            activity_type,
            1.0,
            tags={"player_id": player_id},
            metadata={
                "reputation": reputation,
                "influence": influence_totals
            }
        )

    def track_llm_activity(
        self,
        press_type: str,
        success: bool,
        duration_ms: float,
        persona: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record latency/outcome information for an LLM narrative attempt."""

        tags = {
            "press_type": press_type,
            "success": "true" if success else "false",
        }
        if persona:
            tags["persona"] = persona

        metadata: Dict[str, Any] = {"duration_ms": duration_ms}
        if error:
            metadata["error"] = error

        self.record(
            MetricType.LLM_ACTIVITY,
            press_type,
            duration_ms,
            tags=tags,
            metadata=metadata,
        )

    def track_system_event(
        self,
        event: str,
        *,
        source: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Record internal pause/resume or health events."""

        tags = {}
        if source:
            tags["source"] = source

        metadata = {}
        if reason:
            metadata["reason"] = reason

        self.record(
            MetricType.SYSTEM_EVENT,
            event,
            1.0,
            tags=tags,
            metadata=metadata,
        )

    def track_scholar_stats(
        self,
        scholar_count: int,
        defection_count: int,
        mentorship_count: int,
        avg_confidence: float
    ):
        """Track scholar roster statistics."""
        self.record(
            MetricType.SCHOLAR_STATS,
            "roster_stats",
            float(scholar_count),
            metadata={
                "defection_count": defection_count,
                "mentorship_count": mentorship_count,
                "avg_confidence": avg_confidence
            }
        )

    def track_economy_balance(
        self,
        faction: str,
        total_influence: float,
        player_count: int,
        avg_influence_per_player: float
    ):
        """Track economy balance across factions."""
        self.record(
            MetricType.ECONOMY_BALANCE,
            f"faction_{faction}",
            total_influence,
            tags={"faction": faction},
            metadata={
                "player_count": player_count,
                "avg_per_player": avg_influence_per_player
            }
        )

    def record(
        self,
        metric_type: MetricType,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a metric event."""
        event = MetricEvent(
            timestamp=time.time(),
            metric_type=metric_type,
            name=name,
            value=value,
            tags=tags or {},
            metadata=metadata or {}
        )

        self._metrics_buffer.append(event)

        # Auto-flush if buffer is getting large or enough time has passed
        if len(self._metrics_buffer) >= 100 or \
           time.time() - self._last_flush > self._flush_interval:
            self.flush()

    def flush(self):
        """Flush buffered metrics to database."""
        if not self._metrics_buffer:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                for event in self._metrics_buffer:
                    conn.execute("""
                        INSERT INTO metrics
                        (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        event.timestamp,
                        event.metric_type.value,
                        event.name,
                        event.value,
                        json.dumps(event.tags),
                        json.dumps(event.metadata)
                    ))
                conn.commit()

            logger.info(f"Flushed {len(self._metrics_buffer)} metrics to database")
            self._metrics_buffer.clear()
            self._last_flush = time.time()

        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")

    def get_command_stats(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get command usage statistics."""
        query = """
            SELECT
                name as command,
                COUNT(*) as usage_count,
                AVG(CASE WHEN json_extract(tags, '$.success') = 'True'
                    THEN 1 ELSE 0 END) as success_rate,
                COUNT(DISTINCT json_extract(tags, '$.player_id')) as unique_players
            FROM metrics
            WHERE metric_type = ?
        """
        params = [MetricType.COMMAND_USAGE.value]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " GROUP BY name"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    "usage_count": row[1],
                    "success_rate": row[2],
                    "unique_players": row[3]
                }
            return results

    def get_feature_engagement(
        self,
        days: int = 7
    ) -> Dict[str, Dict[str, Any]]:
        """Get feature engagement statistics for the last N days."""
        start_time = time.time() - (days * 86400)

        query = """
            SELECT
                name as feature,
                COUNT(*) as total_uses,
                COUNT(DISTINCT json_extract(tags, '$.player_id')) as unique_users,
                MAX(timestamp) as last_used
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY name
            ORDER BY total_uses DESC
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.FEATURE_ENGAGEMENT.value,
                start_time
            ])
            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    "total_uses": row[1],
                    "unique_users": row[2],
                    "last_used": datetime.fromtimestamp(row[3]).isoformat()
                }
            return results

    def get_error_summary(
        self,
        hours: int = 24
    ) -> Dict[str, int]:
        """Get error counts for the last N hours."""
        start_time = time.time() - (hours * 3600)

        query = """
            SELECT name, COUNT(*) as error_count
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY name
            ORDER BY error_count DESC
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.ERROR_RATE.value,
                start_time
            ])
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_performance_summary(
        self,
        operation: Optional[str] = None,
        hours: int = 1
    ) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for operations."""
        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                name,
                AVG(value) as avg_duration,
                MIN(value) as min_duration,
                MAX(value) as max_duration,
                COUNT(*) as sample_count
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
        """
        params = [MetricType.PERFORMANCE.value, start_time]

        if operation:
            query += " AND name = ?"
            params.append(operation)

        query += " GROUP BY name"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    "avg_duration_ms": row[1],
                    "min_duration_ms": row[2],
                    "max_duration_ms": row[3],
                    "sample_count": row[4]
                }
            return results

    def get_channel_usage(
        self,
        hours: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """Summarise command usage by channel over the given window."""

        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                COALESCE(json_extract(tags, '$.channel_id'), 'unknown') as channel,
                COUNT(*) as usage_count,
                COUNT(DISTINCT name) as unique_commands,
                COUNT(DISTINCT json_extract(tags, '$.player_id')) as unique_players
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY channel
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.COMMAND_USAGE.value,
                start_time,
            ])
            usage: Dict[str, Dict[str, Any]] = {}
            for row in cursor.fetchall():
                channel_value = row[0]
                channel = str(channel_value) if channel_value not in (None, "") else "unknown"
                usage[channel] = {
                    "usage_count": row[1] or 0,
                    "unique_commands": row[2] or 0,
                    "unique_players": row[3] or 0,
                }
            return usage

    def get_llm_activity_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """Summarise LLM activity over the given window."""

        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                name,
                SUM(CASE WHEN json_extract(tags, '$.success') = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN json_extract(tags, '$.success') = 'false' THEN 1 ELSE 0 END) as failure_count,
                COUNT(*) as total_calls,
                AVG(value) as avg_duration,
                MAX(value) as max_duration
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY name
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.LLM_ACTIVITY.value,
                start_time,
            ])
            summary: Dict[str, Dict[str, Any]] = {}
            for row in cursor.fetchall():
                press_type = row[0]
                successes = row[1] or 0
                failures = row[2] or 0
                total = row[3] or 0
                avg_duration = row[4] or 0.0
                max_duration = row[5] or 0.0

                success_rate = successes / total if total else 0.0

                summary[press_type] = {
                    "total_calls": total,
                    "successes": successes,
                    "failures": failures,
                    "success_rate": success_rate,
                    "avg_duration_ms": avg_duration,
                    "max_duration_ms": max_duration,
                }

            return summary

    def get_system_events(
        self,
        hours: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return recent system events such as pause/resume notifications."""

        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                name,
                timestamp,
                json_extract(tags, '$.source') as source,
                json_extract(metadata, '$.reason') as reason
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.SYSTEM_EVENT.value,
                start_time,
                limit,
            ])
            events = []
            for row in cursor.fetchall():
                events.append(
                    {
                        "event": row[0],
                        "timestamp": datetime.fromtimestamp(row[1]).isoformat(),
                        "source": row[2],
                        "reason": row[3],
                    }
                )
            return events

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive telemetry report."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "uptime_seconds": time.time() - self._start_time,
            "command_stats": self.get_command_stats(),
            "feature_engagement_7d": self.get_feature_engagement(7),
            "errors_24h": self.get_error_summary(24),
            "performance_1h": self.get_performance_summary(hours=1),
            "llm_activity_24h": self.get_llm_activity_summary(24),
            "channel_usage_24h": self.get_channel_usage(24),
            "system_events_24h": self.get_system_events(24, limit=10),
        }

        # Add overall statistics
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_events,
                    COUNT(DISTINCT json_extract(tags, '$.player_id')) as unique_players,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event
                FROM metrics
            """)
            row = cursor.fetchone()
            report["overall"] = {
                "total_events": row[0],
                "unique_players": row[1],
                "first_event": datetime.fromtimestamp(row[2]).isoformat() if row[2] else None,
                "last_event": datetime.fromtimestamp(row[3]).isoformat() if row[3] else None
            }

        return report

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old telemetry data."""
        cutoff_time = time.time() - (days_to_keep * 86400)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff_time,)
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted} old metric events")
        return deleted


# Singleton instance
_telemetry: Optional[TelemetryCollector] = None


def get_telemetry() -> TelemetryCollector:
    """Get or create singleton telemetry collector."""
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryCollector()
    return _telemetry


# Context manager for timing operations
class track_duration:
    """Context manager for tracking operation duration."""

    def __init__(self, operation: str, tags: Optional[Dict[str, str]] = None):
        self.operation = operation
        self.tags = tags or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        telemetry = get_telemetry()
        telemetry.track_performance(self.operation, duration_ms, self.tags)

        # Track error if exception occurred
        if exc_type:
            telemetry.track_error(
                exc_type.__name__,
                command=self.operation,
                error_details=str(exc_val)
            )
