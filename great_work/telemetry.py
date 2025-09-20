"""Telemetry and success metrics tracking for The Great Work."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_env_float(env_key: str, default: float) -> float:
    """Return a float environment variable with a fallback."""

    value = os.getenv(env_key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _status_upper(value: Optional[float], threshold: float) -> Optional[str]:
    """Evaluate metric where higher values are worse."""

    if value is None or threshold <= 0:
        return None
    if value >= threshold:
        return "alert"
    warning_threshold = threshold * 0.75
    if value >= warning_threshold:
        return "warning"
    return "ok"


def _status_lower(value: Optional[float], threshold: float) -> Optional[str]:
    """Evaluate metric where lower values are worse."""

    if value is None or threshold <= 0:
        return None
    if value < threshold:
        return "alert"
    return "ok"


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
    PRESS_CADENCE = "press_cadence"
    DIGEST = "digest"
    QUEUE_DEPTH = "queue_depth"
    ORDER_STATE = "order_state"


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

    def track_press_layer(
        self,
        *,
        layer_type: str,
        event_type: str,
        delay_minutes: float,
        persona: Optional[str] = None,
    ) -> None:
        """Record scheduling of a layered press artefact."""

        tags: Dict[str, str] = {
            "layer_type": layer_type,
            "event_type": event_type,
        }
        if persona:
            tags["persona"] = persona

        metadata = {
            "delay_minutes": delay_minutes,
        }

        self.record(
            MetricType.PRESS_CADENCE,
            layer_type,
            float(delay_minutes),
            tags=tags,
            metadata=metadata,
        )

    def track_digest(
        self,
        *,
        duration_ms: float,
        release_count: int,
        scheduled_queue_size: int,
    ) -> None:
        """Record Gazette digest runtime and output volume."""

        self.record(
            MetricType.DIGEST,
            "gazette_digest",
            duration_ms,
            tags={
                "release_count": str(release_count),
                "scheduled_queue": str(scheduled_queue_size),
            },
            metadata={
                "duration_ms": duration_ms,
                "release_count": release_count,
                "scheduled_queue": scheduled_queue_size,
            },
        )

    def track_queue_depth(
        self,
        queue_size: int,
        *,
        horizon_hours: int,
    ) -> None:
        """Record the size of the scheduled press queue within a time horizon."""

        self.record(
            MetricType.QUEUE_DEPTH,
            "press_queue",
            float(queue_size),
            metadata={"horizon_hours": horizon_hours},
        )

    def track_order_snapshot(
        self,
        *,
        order_type: str,
        event: str,
        pending_count: int,
        oldest_pending_seconds: Optional[float],
    ) -> Dict[str, Optional[str]]:
        """Record dispatcher backlog snapshot for an order type."""

        metadata: Dict[str, Any] = {
            "pending_count": pending_count,
        }
        if oldest_pending_seconds is not None:
            metadata["oldest_pending_seconds"] = float(oldest_pending_seconds)

        self.record(
            MetricType.ORDER_STATE,
            order_type,
            float(pending_count),
            tags={"event": event},
            metadata=metadata,
        )

        pending_threshold = _get_env_float("GREAT_WORK_ALERT_MAX_ORDER_PENDING", 6.0)
        age_threshold_hours = _get_env_float("GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS", 8.0)

        pending_message: Optional[str] = None
        stale_message: Optional[str] = None

        if pending_threshold > 0 and pending_count >= pending_threshold and event in {"enqueue", "poll"}:
            pending_message = (
                f"Dispatcher backlog for {order_type.replace('_', ' ')} at {pending_count} pending (threshold {pending_threshold})."
            )
            self.track_system_event(
                "alert_order_backlog_pending",
                source="dispatcher",
                reason=pending_message,
            )

        if (
            oldest_pending_seconds is not None
            and age_threshold_hours > 0
            and (oldest_pending_seconds / 3600.0) >= age_threshold_hours
            and event == "poll"
        ):
            hours = oldest_pending_seconds / 3600.0
            stale_message = (
                f"Oldest pending {order_type.replace('_', ' ')} order is {hours:.1f}h old "
                f"(threshold {age_threshold_hours:.1f}h)."
            )
            self.track_system_event(
                "alert_order_backlog_stale",
                source="dispatcher",
                reason=stale_message,
            )

        return {
            "pending_alert": pending_message,
            "stale_alert": stale_message,
        }

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

    def get_press_cadence_summary(
        self,
        hours: int = 24,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Summarise layered press generation over the recent window."""

        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                json_extract(tags, '$.event_type') as event_type,
                json_extract(tags, '$.layer_type') as layer_type,
                COUNT(*) as layer_count,
                AVG(value) as avg_delay,
                MAX(value) as max_delay
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY event_type, layer_type
            ORDER BY layer_count DESC
            LIMIT ?
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.PRESS_CADENCE.value,
                start_time,
                limit,
            ])
            summary = []
            for row in cursor.fetchall():
                summary.append(
                    {
                        "event_type": row[0] or "unknown",
                        "layer_type": row[1] or "unknown",
                        "layer_count": int(row[2] or 0),
                        "avg_delay_minutes": float(row[3] or 0.0),
                        "max_delay_minutes": float(row[4] or 0.0),
                    }
                )
            return summary

    def get_digest_summary(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Summarise digest runtimes and queue sizes."""

        start_time = time.time() - (hours * 3600)

        query = """
            SELECT
                COUNT(*) as total_digests,
                AVG(value) as avg_duration,
                MAX(value) as max_duration,
                MIN(value) as min_duration,
                AVG(CAST(json_extract(tags, '$.release_count') AS INTEGER)) as avg_releases,
                MAX(CAST(json_extract(tags, '$.release_count') AS INTEGER)) as max_releases,
                MIN(CAST(json_extract(tags, '$.release_count') AS INTEGER)) as min_releases,
                AVG(CAST(json_extract(tags, '$.scheduled_queue') AS INTEGER)) as avg_queue,
                MAX(CAST(json_extract(tags, '$.scheduled_queue') AS INTEGER)) as max_queue,
                MIN(CAST(json_extract(tags, '$.scheduled_queue') AS INTEGER)) as min_queue
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.DIGEST.value,
                start_time,
            ])
            row = cursor.fetchone()
            if row is None or row[0] == 0:
                return {
                    "total_digests": 0,
                    "avg_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "min_duration_ms": 0.0,
                    "avg_release_count": 0.0,
                    "max_release_count": 0,
                    "min_release_count": 0,
                    "avg_queue_size": 0.0,
                    "max_queue_size": 0,
                    "min_queue_size": 0,
                }
            return {
                "total_digests": int(row[0] or 0),
                "avg_duration_ms": float(row[1] or 0.0),
                "max_duration_ms": float(row[2] or 0.0),
                "min_duration_ms": float(row[3] or 0.0),
                "avg_release_count": float(row[4] or 0.0),
                "max_release_count": int(row[5] or 0),
                "min_release_count": int(row[6] or 0),
                "avg_queue_size": float(row[7] or 0.0),
                "max_queue_size": int(row[8] or 0),
                "min_queue_size": int(row[9] or 0),
            }

    def get_queue_depth_summary(
        self,
        hours: int = 24,
    ) -> Dict[str, Dict[str, float]]:
        """Return aggregate queue depth statistics grouped by horizon."""

        start_time = time.time() - (hours * 3600)
        query = """
            SELECT
                COALESCE(json_extract(metadata, '$.horizon_hours'), 0) as horizon,
                AVG(value) as avg_queue,
                MAX(value) as max_queue,
                COUNT(*) as samples
            FROM metrics
            WHERE metric_type = ? AND timestamp >= ?
            GROUP BY horizon
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, [
                MetricType.QUEUE_DEPTH.value,
                start_time,
            ])
            summary: Dict[str, Dict[str, float]] = {}
            for row in cursor.fetchall():
                horizon = int(row[0] or 0)
                summary[str(horizon)] = {
                    "avg_queue": float(row[1] or 0.0),
                    "max_queue": float(row[2] or 0.0),
                    "samples": float(row[3] or 0.0),
                }
            return summary

    def get_order_backlog_summary(
        self,
        hours: int = 24,
    ) -> Dict[str, Dict[str, Any]]:
        """Summarise dispatcher backlog metrics by order type."""

        start_time = time.time() - (hours * 3600)
        summary: Dict[str, Dict[str, Any]] = {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                    SELECT
                        name,
                        AVG(value) as avg_pending,
                        MAX(value) as max_pending,
                        MIN(value) as min_pending,
                        AVG(CAST(json_extract(metadata, '$.oldest_pending_seconds') AS REAL)) as avg_oldest,
                        MAX(CAST(json_extract(metadata, '$.oldest_pending_seconds') AS REAL)) as max_oldest,
                        MIN(CAST(json_extract(metadata, '$.oldest_pending_seconds') AS REAL)) as min_oldest
                    FROM metrics
                    WHERE metric_type = ? AND timestamp >= ?
                    GROUP BY name
                """,
                (
                    MetricType.ORDER_STATE.value,
                    start_time,
                ),
            )
            for row in cursor.fetchall():
                order_type = row[0]
                summary[order_type] = {
                    "avg_pending": float(row[1] or 0.0),
                    "max_pending": float(row[2] or 0.0),
                    "min_pending": float(row[3] or 0.0),
                    "avg_oldest_seconds": float(row[4] or 0.0),
                    "max_oldest_seconds": float(row[5] or 0.0),
                    "min_oldest_seconds": float(row[6] or 0.0),
                }

            if summary:
                for order_type in list(summary.keys()):
                    row = conn.execute(
                        """
                            SELECT
                                value,
                                json_extract(metadata, '$.oldest_pending_seconds') as oldest_seconds,
                                timestamp
                            FROM metrics
                            WHERE metric_type = ? AND name = ?
                            ORDER BY timestamp DESC
                            LIMIT 1
                        """,
                        (
                            MetricType.ORDER_STATE.value,
                            order_type,
                        ),
                    ).fetchone()
                    if row:
                        latest_pending = float(row[0] or 0.0)
                        oldest_seconds = row[1]
                        latest_timestamp = datetime.fromtimestamp(row[2]).isoformat()
                    else:
                        latest_pending = summary[order_type]["max_pending"]
                        oldest_seconds = summary[order_type]["max_oldest_seconds"]
                        latest_timestamp = None

                    summary[order_type]["latest_pending"] = latest_pending
                    summary[order_type]["latest_oldest_seconds"] = (
                        float(oldest_seconds) if oldest_seconds is not None else 0.0
                    )
                    summary[order_type]["latest_timestamp"] = latest_timestamp

        return summary

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
            "press_cadence_24h": self.get_press_cadence_summary(24, limit=10),
            "digest_health_24h": self.get_digest_summary(24),
            "queue_depth_24h": self.get_queue_depth_summary(24),
            "order_backlog_24h": self.get_order_backlog_summary(24),
            "symposium": self.get_symposium_metrics(24),
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

        report["health"] = self.evaluate_health(report)

        return report

    def evaluate_health(self, report_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate telemetry signals against alert thresholds."""

        data = report_data or {}
        digest_stats = data.get("digest_health_24h") or self.get_digest_summary(24)
        queue_summary = data.get("queue_depth_24h") or self.get_queue_depth_summary(24)
        llm_stats = data.get("llm_activity_24h") or self.get_llm_activity_summary(24)

        thresholds = {
            "digest_ms": _get_env_float("GREAT_WORK_ALERT_MAX_DIGEST_MS", 5000.0),
            "min_releases": _get_env_float("GREAT_WORK_ALERT_MIN_RELEASES", 1.0),
            "queue_size": _get_env_float("GREAT_WORK_ALERT_MAX_QUEUE", 12.0),
            "llm_latency_ms": _get_env_float("GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS", 4000.0),
            "llm_failure_rate": _get_env_float("GREAT_WORK_ALERT_LLM_FAILURE_RATE", 0.2),
            "order_pending": _get_env_float("GREAT_WORK_ALERT_MAX_ORDER_PENDING", 6.0),
            "order_age_hours": _get_env_float("GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS", 8.0),
        }

        checks: List[Dict[str, Any]] = []
        counts = {"ok": 0, "warning": 0, "alert": 0}

        def _register(metric: str, label: str, status: Optional[str], detail: str, *,
                      observed: Optional[float] = None,
                      threshold: Optional[float] = None,
                      window: str = "24h") -> None:
            if status is None:
                return
            counts[status] += 1
            checks.append(
                {
                    "metric": metric,
                    "label": label,
                    "status": status,
                    "detail": detail,
                    "observed": observed,
                    "threshold": threshold,
                    "window": window,
                }
            )

        if digest_stats.get("total_digests", 0) > 0:
            max_runtime = digest_stats.get("max_duration_ms") or 0.0
            runtime_status = _status_upper(max_runtime, thresholds["digest_ms"])
            _register(
                "digest_runtime",
                "Digest runtime",
                runtime_status,
                f"Max runtime {max_runtime:.0f} ms (threshold {thresholds['digest_ms']:.0f} ms)",
                observed=max_runtime,
                threshold=thresholds["digest_ms"],
            )

            min_releases = digest_stats.get("min_release_count")
            release_status = _status_lower(min_releases, thresholds["min_releases"])
            if release_status == "alert":
                _register(
                    "digest_release_floor",
                    "Digest release count",
                    release_status,
                    f"Lowest digest published {min_releases} items (expected ≥ {int(thresholds['min_releases'])})",
                    observed=float(min_releases or 0.0),
                    threshold=thresholds["min_releases"],
                )
            else:
                _register(
                    "digest_release_floor",
                    "Digest release count",
                    release_status,
                    f"Lowest digest published {min_releases} items",
                    observed=float(min_releases or 0.0),
                    threshold=thresholds["min_releases"],
                )

        if queue_summary:
            worst_horizon: Optional[str] = None
            worst_stats: Optional[Dict[str, float]] = None
            for horizon, stats in queue_summary.items():
                if worst_stats is None or stats.get("max_queue", 0.0) > worst_stats.get("max_queue", 0.0):
                    worst_horizon = horizon
                    worst_stats = stats
            if worst_stats is not None:
                max_queue = worst_stats.get("max_queue", 0.0)
                queue_status = _status_upper(max_queue, thresholds["queue_size"])
                horizon_label = f"≤{worst_horizon}h" if worst_horizon is not None else "queue"
                avg_queue = worst_stats.get("avg_queue", 0.0)
                _register(
                    "press_queue_depth",
                    f"Press queue {horizon_label}",
                    queue_status,
                    f"Max pending {max_queue:.0f} (avg {avg_queue:.1f})",
                    observed=max_queue,
                    threshold=thresholds["queue_size"],
                )

        total_calls = 0
        total_successes = 0
        weighted_latency_sum = 0.0
        max_latency = 0.0
        for stats in llm_stats.values():
            calls = stats.get("total_calls", 0)
            successes = stats.get("successes", 0)
            total_calls += calls
            total_successes += successes
            avg_latency = stats.get("avg_duration_ms", 0.0)
            weighted_latency_sum += avg_latency * calls
            max_latency = max(max_latency, stats.get("max_duration_ms", 0.0))

        if total_calls > 0:
            overall_avg_latency = weighted_latency_sum / total_calls if total_calls else 0.0
            latency_status = _status_upper(overall_avg_latency, thresholds["llm_latency_ms"])
            _register(
                "llm_latency",
                "LLM latency",
                latency_status,
                f"Avg {overall_avg_latency:.0f} ms (max {max_latency:.0f} ms across {total_calls} calls)",
                observed=overall_avg_latency,
                threshold=thresholds["llm_latency_ms"],
            )

            failure_rate = 1.0 - (total_successes / total_calls)
            failure_status = _status_upper(failure_rate, thresholds["llm_failure_rate"])
            _register(
                "llm_failure_rate",
                "LLM failure rate",
                failure_status,
                f"{failure_rate:.0%} failures across {total_calls} calls",
                observed=failure_rate,
                threshold=thresholds["llm_failure_rate"],
            )

        order_summary = data.get("order_backlog_24h") or self.get_order_backlog_summary(24)
        if order_summary:
            # Determine the order type with the highest current pending count
            worst_pending_type, worst_pending_stats = max(
                order_summary.items(),
                key=lambda item: item[1].get("latest_pending", 0.0),
            )
            latest_pending = worst_pending_stats.get("latest_pending", 0.0)
            pending_status = _status_upper(latest_pending, thresholds["order_pending"])
            pretty_type = worst_pending_type.replace("_", " ")
            _register(
                "order_pending",
                f"Dispatcher backlog ({pretty_type})",
                pending_status,
                f"Current pending {latest_pending:.0f} (max {worst_pending_stats.get('max_pending', 0.0):.0f})",
                observed=latest_pending,
                threshold=thresholds["order_pending"],
            )

            worst_stale_type, worst_stale_stats = max(
                order_summary.items(),
                key=lambda item: item[1].get("latest_oldest_seconds", 0.0),
            )
            oldest_hours = (
                worst_stale_stats.get("latest_oldest_seconds", 0.0) / 3600.0
            )
            staleness_status = _status_upper(oldest_hours, thresholds["order_age_hours"])
            pretty_stale = worst_stale_type.replace("_", " ")
            _register(
                "order_staleness",
                f"Oldest pending order ({pretty_stale})",
                staleness_status,
                f"Oldest pending age {oldest_hours:.1f}h",
                observed=oldest_hours,
                threshold=thresholds["order_age_hours"],
            )

        return {
            "checks": checks,
            "status_counts": counts,
            "thresholds": thresholds,
        }

    def get_symposium_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Summarise symposium scoring and debt telemetry."""

        start_time = time.time() - (hours * 3600)
        scoring_entries: List[Dict[str, Any]] = []
        scoring_count = 0
        debt_by_player: Dict[str, Dict[str, Any]] = {}
        reprisal_counts: Dict[str, Dict[str, Any]] = {}

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT COUNT(*), AVG(value)
                       FROM metrics
                       WHERE metric_type = ? AND name = ? AND timestamp >= ?""",
                (
                    MetricType.GAME_PROGRESSION.value,
                    "symposium_score",
                    start_time,
                ),
            ).fetchone()
            if row:
                scoring_count = int(row[0] or 0)
                average_score = float(row[1] or 0.0) if scoring_count else 0.0
            else:
                scoring_count = 0
                average_score = 0.0

            cursor = conn.execute(
                """SELECT value,
                               json_extract(tags, '$.player_id') AS player_id,
                               json_extract(metadata, '$.proposal_id') AS proposal_id,
                               json_extract(metadata, '$.age_days') AS age_days,
                               timestamp
                        FROM metrics
                        WHERE metric_type = ? AND name = ? AND timestamp >= ?
                        ORDER BY value DESC
                        LIMIT 10""",
                (
                    MetricType.GAME_PROGRESSION.value,
                    "symposium_score",
                    start_time,
                ),
            )
            for row in cursor.fetchall():
                scoring_entries.append(
                    {
                        "score": float(row[0] or 0.0),
                        "player_id": row[1],
                        "proposal_id": row[2],
                        "age_days": float(row[3] or 0.0),
                        "recorded_at": datetime.fromtimestamp(row[4]).isoformat(),
                    }
                )

            cursor = conn.execute(
                """SELECT value,
                               json_extract(tags, '$.player_id') AS player_id,
                               json_extract(metadata, '$.faction') AS faction,
                               timestamp
                        FROM metrics
                        WHERE metric_type = ? AND name = ? AND timestamp >= ?
                        ORDER BY timestamp DESC""",
                (
                    MetricType.GAME_PROGRESSION.value,
                    "symposium_debt_outstanding",
                    start_time,
                ),
            )
            for value, player_id, faction, ts in cursor.fetchall():
                if not player_id:
                    continue
                if player_id in debt_by_player:
                    continue
                debt_by_player[player_id] = {
                    "debt": float(value or 0.0),
                    "faction": faction,
                    "recorded_at": datetime.fromtimestamp(ts).isoformat(),
                }

            cursor = conn.execute(
                """SELECT value,
                               json_extract(tags, '$.player_id') AS player_id,
                               json_extract(metadata, '$.faction') AS faction,
                               json_extract(metadata, '$.reprisal_level') AS level,
                               timestamp
                        FROM metrics
                        WHERE metric_type = ? AND name = ? AND timestamp >= ?""",
                (
                    MetricType.GAME_PROGRESSION.value,
                    "symposium_debt_reprisal",
                    start_time,
                ),
            )
            for value, player_id, faction, level, ts in cursor.fetchall():
                if not player_id:
                    continue
                summary = reprisal_counts.setdefault(
                    player_id,
                    {
                        "count": 0,
                        "total_penalty": 0.0,
                        "factions": set(),
                        "last_reprisal_at": None,
                    },
                )
                summary["count"] += 1
                summary["total_penalty"] += float(value or 0.0)
                if faction:
                    summary["factions"].add(faction)
                summary["last_reprisal_at"] = datetime.fromtimestamp(ts).isoformat()

        reprisal_summary: List[Dict[str, Any]] = []
        for player_id, data in reprisal_counts.items():
            reprisal_summary.append(
                {
                    "player_id": player_id,
                    "count": data["count"],
                    "total_penalty": data["total_penalty"],
                    "factions": sorted(data["factions"]),
                    "last_reprisal_at": data["last_reprisal_at"],
                }
            )
        reprisal_summary.sort(key=lambda item: item["count"], reverse=True)

        debt_list = [
            {
                "player_id": player_id,
                "debt": details["debt"],
                "faction": details.get("faction"),
                "recorded_at": details.get("recorded_at"),
            }
            for player_id, details in debt_by_player.items()
        ]
        debt_list.sort(key=lambda item: item["debt"], reverse=True)

        return {
            "scoring": {
                "average": average_score,
                "count": scoring_count,
                "top": scoring_entries,
            },
            "debts": debt_list,
            "reprisals": reprisal_summary,
        }

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
