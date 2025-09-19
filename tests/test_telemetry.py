"""Tests for telemetry and metrics tracking."""
import pytest
import tempfile
import time
import json
from pathlib import Path

from great_work.telemetry import (
    MetricType,
    MetricEvent,
    TelemetryCollector,
    get_telemetry,
    track_duration
)


def test_metric_event_creation():
    """Test MetricEvent dataclass creation."""
    event = MetricEvent(
        timestamp=time.time(),
        metric_type=MetricType.COMMAND_USAGE,
        name="test_command",
        value=1.0,
        tags={"player": "test"},
        metadata={"duration": 100}
    )

    assert event.metric_type == MetricType.COMMAND_USAGE
    assert event.name == "test_command"
    assert event.value == 1.0
    assert event.tags["player"] == "test"
    assert event.metadata["duration"] == 100


def test_telemetry_collector_init():
    """Test TelemetryCollector initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_telemetry.db"
        collector = TelemetryCollector(db_path)

        assert collector.db_path == db_path
        assert db_path.exists()
        assert len(collector._metrics_buffer) == 0


def test_track_command():
    """Test command tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_command(
            command_name="theory",
            player_id="player1",
            guild_id="guild1",
            success=True,
            duration_ms=150.5
        )

        assert len(collector._metrics_buffer) == 1
        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.COMMAND_USAGE
        assert event.name == "theory"
        assert event.tags["player_id"] == "player1"
        assert event.tags["success"] == "True"
        assert event.metadata["duration_ms"] == 150.5


def test_track_feature_usage():
    """Test feature usage tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_feature_usage(
            feature_name="conference",
            player_id="player2",
            details={"confidence": "certain"}
        )

        assert len(collector._metrics_buffer) == 1
        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.FEATURE_ENGAGEMENT
        assert event.name == "conference"
        assert event.metadata["confidence"] == "certain"


def test_track_game_progression():
    """Test game progression tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_game_progression(
            event_name="expedition_success",
            value=3.0,
            player_id="player3",
            details={"type": "great_project"}
        )

        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.GAME_PROGRESSION
        assert event.value == 3.0
        assert event.tags["player_id"] == "player3"


def test_track_error():
    """Test error tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_error(
            error_type="ValidationError",
            command="expedition",
            player_id="player4",
            error_details="Invalid expedition type"
        )

        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.ERROR_RATE
        assert event.name == "ValidationError"
        assert event.tags["command"] == "expedition"


def test_track_performance():
    """Test performance metric tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_performance(
            operation="database_query",
            duration_ms=45.2,
            tags={"query": "select_scholars"}
        )

        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.PERFORMANCE
        assert event.value == 45.2
        assert event.tags["query"] == "select_scholars"


def test_flush_metrics():
    """Test flushing metrics to database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Add some metrics
        for i in range(5):
            collector.track_command(
                f"command_{i}",
                f"player_{i}",
                "guild1",
                success=True
            )

        assert len(collector._metrics_buffer) == 5

        # Flush to database
        collector.flush()
        assert len(collector._metrics_buffer) == 0

        # Verify data was written
        stats = collector.get_command_stats()
        assert len(stats) == 5
        assert "command_0" in stats


def test_auto_flush():
    """Test automatic flushing when buffer is full."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Add enough metrics to trigger auto-flush (100+)
        for i in range(101):
            collector.record(
                MetricType.COMMAND_USAGE,
                f"cmd_{i}",
                1.0
            )

        # Should have auto-flushed
        assert len(collector._metrics_buffer) < 100


def test_get_command_stats():
    """Test retrieving command statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Track some commands
        collector.track_command("theory", "p1", "g1", True)
        collector.track_command("theory", "p2", "g1", True)
        collector.track_command("expedition", "p1", "g1", True)
        collector.track_command("expedition", "p1", "g1", False)
        collector.flush()

        stats = collector.get_command_stats()

        assert stats["theory"]["usage_count"] == 2
        assert stats["theory"]["success_rate"] == 1.0
        assert stats["theory"]["unique_players"] == 2

        assert stats["expedition"]["usage_count"] == 2
        assert stats["expedition"]["success_rate"] == 0.5
        assert stats["expedition"]["unique_players"] == 1


def test_get_feature_engagement():
    """Test retrieving feature engagement stats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Track features
        collector.track_feature_usage("conference", "p1")
        collector.track_feature_usage("conference", "p2")
        collector.track_feature_usage("symposium", "p1")
        collector.flush()

        engagement = collector.get_feature_engagement(days=1)

        assert engagement["conference"]["total_uses"] == 2
        assert engagement["conference"]["unique_users"] == 2
        assert engagement["symposium"]["total_uses"] == 1


def test_get_error_summary():
    """Test retrieving error summary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Track errors
        collector.track_error("ValueError", "theory")
        collector.track_error("ValueError", "expedition")
        collector.track_error("KeyError", "status")
        collector.flush()

        errors = collector.get_error_summary(hours=1)

        assert errors["ValueError"] == 2
        assert errors["KeyError"] == 1


def test_track_duration_context():
    """Test track_duration context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import great_work.telemetry
        # Set up a test collector
        great_work.telemetry._telemetry = TelemetryCollector(Path(tmpdir) / "test.db")

        with track_duration("test_operation", {"type": "test"}):
            time.sleep(0.01)  # Simulate some work

        collector = get_telemetry()
        assert len(collector._metrics_buffer) == 1
        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.PERFORMANCE
        assert event.name == "test_operation"
        assert event.value > 10  # Should be > 10ms


def test_generate_report():
    """Test comprehensive report generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Add various metrics
        collector.track_command("theory", "p1", "g1", True)
        collector.track_feature_usage("conference", "p1")
        collector.track_error("TestError")
        collector.track_performance("query", 50.0)
        collector.flush()

        report = collector.generate_report()

        assert "generated_at" in report
        assert "uptime_seconds" in report
        assert "command_stats" in report
        assert "feature_engagement_7d" in report
        assert "errors_24h" in report
        assert "performance_1h" in report
        assert report["overall"]["total_events"] == 4


def test_cleanup_old_data():
    """Test cleanup of old telemetry data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        # Add old and new metrics
        old_time = time.time() - (40 * 86400)  # 40 days ago
        new_time = time.time()

        collector._metrics_buffer = [
            MetricEvent(old_time, MetricType.COMMAND_USAGE, "old", 1.0),
            MetricEvent(new_time, MetricType.COMMAND_USAGE, "new", 1.0),
        ]
        collector.flush()

        # Clean up data older than 30 days
        deleted = collector.cleanup_old_data(days_to_keep=30)

        assert deleted == 1

        # Verify only new data remains
        stats = collector.get_command_stats()
        assert "new" in stats
        assert "old" not in stats


def test_singleton_pattern():
    """Test singleton pattern for telemetry collector."""
    import great_work.telemetry
    # Reset singleton
    great_work.telemetry._telemetry = None

    collector1 = get_telemetry()
    collector2 = get_telemetry()

    assert collector1 is collector2