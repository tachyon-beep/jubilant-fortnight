"""Tests for telemetry and metrics tracking."""
import pytest
import tempfile
import time
import json
from pathlib import Path

from great_work.alerting import AlertRouter, set_alert_router
from great_work.telemetry import (
    MetricType,
    MetricEvent,
    TelemetryCollector,
    get_telemetry,
    track_duration
)
from great_work.tools.recommend_kpi_thresholds import recommend_thresholds
from great_work.tools.recommend_seasonal_settings import recommend_settings as recommend_seasonal_settings


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
            duration_ms=150.5,
            channel_id="chan1",
        )

        assert len(collector._metrics_buffer) == 1
        event = collector._metrics_buffer[0]
        assert event.metric_type == MetricType.COMMAND_USAGE
        assert event.name == "theory"
        assert event.tags["player_id"] == "player1"
        assert event.tags["success"] == "True"
        assert event.metadata["duration_ms"] == 150.5
        assert event.tags["channel_id"] == "chan1"


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


def test_track_press_layer_and_summary():
    """Press cadence metrics should aggregate by event and layer type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "press.db")

        collector.track_press_layer(
            layer_type="academic_gossip",
            event_type="expedition",
            delay_minutes=45.0,
            persona="Scholar"
        )
        collector.track_press_layer(
            layer_type="academic_gossip",
            event_type="expedition",
            delay_minutes=15.0,
        )
        collector.flush()

        summary = collector.get_press_cadence_summary(hours=1)
        assert summary
        top = summary[0]
        assert top["event_type"] == "expedition"
        assert top["layer_type"] == "academic_gossip"
        assert top["layer_count"] == 2
        assert top["avg_delay_minutes"] > 0


def test_track_queue_depth_and_summary():
    """Queue depth metrics should aggregate by horizon."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "queue.db")

        collector.track_queue_depth(3, horizon_hours=48)
        collector.track_queue_depth(1, horizon_hours=24)
        collector.track_queue_depth(5, horizon_hours=48)
        collector.flush()

        summary = collector.get_queue_depth_summary(hours=1)
        assert summary
        assert "48" in summary
        assert summary["48"]["max_queue"] == 5
        assert summary["24"]["avg_queue"] == 1.0


def test_track_order_snapshot_and_summary():
    """Dispatcher backlog snapshots should surface latest and max pending counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "orders.db")

        alerts = collector.track_order_snapshot(
            order_type="mentorship_activation",
            event="enqueue",
            pending_count=3,
            oldest_pending_seconds=3600.0,
        )
        assert alerts["pending_alert"] is None  # enqueue alone does not trigger admin notifier logic
        collector.track_order_snapshot(
            order_type="mentorship_activation",
            event="update:completed",
            pending_count=2,
            oldest_pending_seconds=1800.0,
        )
        collector.track_order_snapshot(
            order_type="conference_resolution",
            event="enqueue",
            pending_count=1,
            oldest_pending_seconds=None,
        )
        collector.flush()

        summary = collector.get_order_backlog_summary(hours=1)
        assert summary
        assert "mentorship_activation" in summary
        stats = summary["mentorship_activation"]
        assert stats["latest_pending"] == 2.0
        assert stats["max_pending"] == 3.0
        assert stats["latest_oldest_seconds"] == 1800.0
        assert "conference_resolution" in summary
        assert summary["conference_resolution"]["latest_pending"] == 1.0


def test_get_order_backlog_events_filters_and_limits():
    """Raw dispatcher backlog events should support filtering and limits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "orders.db")

        # Simulate interleaved order events
        for pending in (3, 2, 1):
            collector.track_order_snapshot(
                order_type="mentorship_activation",
                event="poll",
                pending_count=pending,
                oldest_pending_seconds=3600.0 * pending,
            )
        collector.track_order_snapshot(
            order_type="conference_resolution",
            event="poll",
            pending_count=5,
            oldest_pending_seconds=900.0,
        )
        collector.track_order_snapshot(
            order_type="mentorship_activation",
            event="update:completed",
            pending_count=0,
            oldest_pending_seconds=0.0,
        )
        collector.flush()

        records = collector.get_order_backlog_events(order_type="mentorship_activation", hours=1, limit=5)
        assert records
        assert all(record["order_type"] == "mentorship_activation" for record in records)
        assert records[0]["event"] == "update:completed"

        limited = collector.get_order_backlog_events(hours=1, limit=2)
        assert len(limited) == 2

        high_pending = collector.get_order_backlog_events(hours=1, min_pending=3)
        assert all(record["pending"] >= 3 for record in high_pending)

        aged = collector.get_order_backlog_events(hours=1, min_age_seconds=3500)
        assert aged and all((record["oldest_pending_seconds"] or 0) >= 3500 for record in aged)

        completed = collector.get_order_backlog_events(
            hours=1,
            event="update:completed",
            order_type="mentorship_activation",
        )
        assert completed and all(record["event"] == "update:completed" for record in completed)


def test_track_moderation_event_summary(tmp_path):
    collector = TelemetryCollector(Path(tmp_path) / "moderation.db")
    collector.track_moderation_event(
        surface="press",
        stage="llm_output",
        category="Hate",
        severity="block",
        actor="mod",
        text_hash="abc",
        source="guardian",
    )
    collector.track_moderation_event(
        surface="status",
        stage="player_input",
        category="Profanity",
        severity="warn",
        actor="player",
        text_hash="def",
        source="prefilter",
    )
    collector.flush()

    summary = collector.get_moderation_summary(hours=1)
    assert summary["totals"]["count"] == 2
    assert summary["totals"]["by_category"]["Hate"] == 1
    assert summary["totals"]["by_severity"]["block"] == 1


def test_track_system_event_alert_routing(monkeypatch):
    """Alert-prefixed system events trigger the alert router with cooldown handling."""
    monkeypatch.setenv("GREAT_WORK_ALERT_COOLDOWN_SECONDS", "60")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "alerts.db")

        calls = []

        class DummyRouter:
            def notify(self, **kwargs):
                calls.append(kwargs)
                return True

        set_alert_router(DummyRouter())
        try:
            collector.track_system_event(
                "alert_dispatcher_pending",
                source="dispatcher",
                reason="Pending orders exceeded threshold",
            )
            # Second emit within cooldown should not trigger router
            collector.track_system_event(
                "alert_dispatcher_pending",
                source="dispatcher",
                reason="Pending still high",
            )
            assert len(calls) == 1

            # Expire cooldown manually and emit again
            collector._alert_history["alert_dispatcher_pending"] = time.time() - 120
            collector.track_system_event(
                "alert_dispatcher_pending",
                source="dispatcher",
                reason="Pending recovered",
            )
            assert len(calls) == 2
            assert calls[0]["severity"] == "warning"
        finally:
            set_alert_router(None)


def test_alert_router_email_delivery(monkeypatch):
    """Alert router should deliver email notifications when SMTP config is present."""

    sent_messages = []

    class DummySMTP:
        started_tls = False
        logged_in = False

        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout

        def starttls(self):
            DummySMTP.started_tls = True

        def login(self, username, password):
            DummySMTP.logged_in = True

        def send_message(self, message):
            sent_messages.append(message)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("smtplib.SMTP", DummySMTP)

    router = AlertRouter(
        email_host="smtp.example.com",
        email_port=587,
        email_username="user",
        email_password="pass",
        email_from="alerts@example.com",
        email_recipients=["ops@example.com"],
        email_use_tls=True,
    )

    routed = router.notify(
        event="alert_test_event",
        message="Test alert",
        severity="critical",
        source="unit-test",
        metadata={"foo": "bar"},
    )

    assert routed is True
    assert sent_messages, "Expected email to be sent"
    email = sent_messages[0]
    assert "alert_test_event" in email["Subject"]
    assert "alerts@example.com" == email["From"]
    assert "ops@example.com" in email["To"]
    assert DummySMTP.started_tls is True
    assert DummySMTP.logged_in is True


def test_alert_router_multiple_webhooks(monkeypatch):
    """Router should fan out to every configured webhook URL."""

    urls_called = []

    def fake_post(self, payload, url):
        urls_called.append(url)
        return True

    monkeypatch.setattr(AlertRouter, "_post_webhook", fake_post, raising=False)

    router = AlertRouter(webhook_urls=["https://ops.example", "https://alerts.example"])
    router.notify(event="test", message="Hello", severity="warning")

    assert urls_called == ["https://ops.example", "https://alerts.example"]


def test_digest_summary():
    """Digest summaries should surface runtime and queue size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "digest.db")

        collector.track_digest(
            duration_ms=1200.0,
            release_count=3,
            scheduled_queue_size=5,
        )
        collector.flush()

        digest = collector.get_digest_summary(hours=1)
        assert digest["total_digests"] == 1
        assert digest["avg_duration_ms"] == 1200.0
        assert digest["avg_release_count"] == 3.0
        assert digest["avg_queue_size"] == 5.0
        assert digest["min_duration_ms"] == 1200.0
        assert digest["min_release_count"] == 3
        assert digest["min_queue_size"] == 5


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


def test_product_kpis_and_health(monkeypatch):
    """Product KPI aggregation should inform health checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "kpi.db")

        # Two active players issue commands within the window.
        collector.track_command(
            command_name="expedition",
            player_id="player_a",
            guild_id="guild",
            success=True,
        )
        collector.track_command(
            command_name="symposium",
            player_id="player_b",
            guild_id="guild",
            success=True,
        )

        # Only one of them publishes a manifesto, and one archive lookup occurs.
        collector.track_game_progression(
            event_name="manifesto_generated",
            value=1.0,
            player_id="player_a",
            details={"expedition_type": "field"},
        )
        collector.track_game_progression(
            event_name="archive_lookup",
            value=1.0,
            player_id="player_b",
            details={"search": "Code"},
        )
        collector.track_game_progression(
            event_name="nickname_adopted",
            value=1.0,
            player_id="player_a",
            details={"scholar_id": "SCH-001"},
        )
        collector.track_game_progression(
            event_name="press_shared",
            value=1.0,
            player_id="player_b",
            details={"press_id": 1},
        )

        collector.flush()

        kpis = collector.get_product_kpis()
        engagement = kpis["engagement"]
        assert engagement["active_players_24h"] == 2.0
        assert engagement["command_count_24h"] == 2.0
        manifestos = kpis["manifestos"]
        assert manifestos["manifesto_players_7d"] == 1.0
        archive = kpis["archive"]
        assert archive["lookup_players_7d"] == 1.0

        # Configure thresholds high enough to trigger alerts for the sample data.
        monkeypatch.setenv("GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS", "4")
        monkeypatch.setenv("GREAT_WORK_ALERT_MIN_MANIFESTO_RATE", "0.9")
        monkeypatch.setenv("GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS", "3")
        monkeypatch.setenv("GREAT_WORK_ALERT_MIN_NICKNAME_RATE", "0.9")
        monkeypatch.setenv("GREAT_WORK_ALERT_MIN_PRESS_SHARES", "5")

        report_stub = {
            "digest_health_24h": {"total_digests": 0},
            "queue_depth_24h": {},
            "llm_activity_24h": {},
            "order_backlog_24h": {},
            "symposium": {"scoring": {}, "debts": [], "reprisals": []},
            "economy": {"investments": {}, "endowments": {}, "commitments": {}},
            "product_kpis": kpis,
        }

        health = collector.evaluate_health(report_stub)
        metrics = {entry["metric"]: entry["status"] for entry in health["checks"]}

        assert metrics.get("active_players") == "alert"
        assert metrics.get("manifesto_adoption") == "alert"
        assert metrics.get("archive_usage") == "alert"
        assert metrics.get("nickname_rate") == "alert"
        assert metrics.get("press_shares") == "alert"


def test_product_kpi_history():
    """Daily KPI history should capture per-day trends."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "history.db"
        collector = TelemetryCollector(db_path)
        collector.flush()

        import sqlite3
        import time

        now = time.time()

        with sqlite3.connect(db_path) as conn:
            for day_offset in range(3):
                ts = now - day_offset * 86400
                conn.execute(
                    """
                        INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        MetricType.COMMAND_USAGE.value,
                        "command",
                        1.0,
                        json.dumps({"player_id": f"player_{day_offset}"}),
                        json.dumps({}),
                    ),
                )
                conn.execute(
                    """
                        INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        MetricType.GAME_PROGRESSION.value,
                        "manifesto_generated",
                        1.0,
                        json.dumps({"player_id": f"player_{day_offset}"}),
                        json.dumps({}),
                    ),
                )
                conn.execute(
                    """
                        INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        MetricType.GAME_PROGRESSION.value,
                        "archive_lookup",
                        1.0,
                        json.dumps({"player_id": f"player_{day_offset}"}),
                        json.dumps({}),
                        ),
                )
                conn.execute(
                    """
                        INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        MetricType.GAME_PROGRESSION.value,
                        "nickname_adopted",
                        1.0,
                        json.dumps({"player_id": f"player_{day_offset}"}),
                        json.dumps({}),
                    ),
                )
                conn.execute(
                    """
                        INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        MetricType.GAME_PROGRESSION.value,
                        "press_shared",
                        1.0,
                        json.dumps({"player_id": f"player_{day_offset}"}),
                        json.dumps({}),
                    ),
                )
            conn.commit()

        history = collector.get_product_kpi_history(days=7)
        daily = history["daily"]
        assert len(daily) == 3
        assert daily[-1]["active_players"] == 1
        assert daily[-1]["manifesto_events"] == 1
        assert daily[-1]["archive_events"] == 1
        assert daily[-1]["nickname_events"] == 1
        assert daily[-1]["press_share_events"] == 1


def test_recommend_kpi_thresholds(tmp_path):
    """Threshold recommendation script should reflect recorded telemetry."""
    db_path = tmp_path / "telemetry.db"
    collector = TelemetryCollector(db_path)
    collector.flush()

    import sqlite3
    import time
    from great_work.tools.recommend_kpi_thresholds import recommend_thresholds

    now = time.time()

    def _insert(ts, metric_type, name, value, tags, metadata):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, metric_type, name, value, json.dumps(tags), json.dumps(metadata)),
            )
            conn.commit()

    # Three days of command usage across varying player counts.
    daily_players = [
        ["alice", "bob", "carol"],
        ["alice", "bob"],
        ["alice", "dave", "eve"],
    ]

    for offset, players in enumerate(daily_players):
        ts = now - offset * 86400 + 5
        for player in players:
            _insert(
                ts,
                MetricType.COMMAND_USAGE.value,
                "command_test",
                1.0,
                {"player_id": player},
                {},
            )

    # Manifesto adoption for two players.
    for player in ("alice", "carol"):
        _insert(
            now - 3600,
            MetricType.GAME_PROGRESSION.value,
            "manifesto_generated",
            1.0,
            {"player_id": player},
            {},
        )

    # Six archive lookups over the window.
    for idx in range(6):
        _insert(
            now - idx * 3600,
            MetricType.GAME_PROGRESSION.value,
            "archive_lookup",
            1.0,
            {"player_id": "alice"},
            {},
        )

    recommendations = recommend_thresholds(
        db_path,
        engagement_days=7,
        manifesto_days=14,
        archive_days=14,
    )

    assert recommendations["GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS"] == pytest.approx(1.87, rel=0.01)
    assert recommendations["GREAT_WORK_ALERT_MIN_MANIFESTO_RATE"] == 0.32
    assert recommendations["GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS"] == 1.0
    assert "GREAT_WORK_ALERT_MIN_NICKNAME_RATE" in recommendations
    assert "GREAT_WORK_ALERT_MIN_PRESS_SHARES" in recommendations


def test_recommend_seasonal_settings(tmp_path):
    """Seasonal recommendation helper summarises debts and thresholds."""
    db_path = tmp_path / "telemetry.db"
    collector = TelemetryCollector(db_path)
    collector.flush()

    import sqlite3
    import time

    now = time.time()
    with sqlite3.connect(db_path) as conn:
        for idx, debt in enumerate((6.0, 4.0, 2.0)):
            conn.execute(
                """
                    INSERT INTO metrics (timestamp, metric_type, name, value, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now - idx * 86400,
                    MetricType.GAME_PROGRESSION.value,
                    "seasonal_commitment_status",
                    debt,
                    json.dumps({"player_id": f"player_{idx}"}),
                    json.dumps(
                        {
                            "remaining_debt": debt,
                            "threshold": 4 + idx,
                            "days_remaining": 14 - idx,
                        }
                    ),
                ),
            )
        conn.commit()

    summary = recommend_seasonal_settings(db_path, days=14)
    assert summary["players_sampled"] == 3
    assert summary["average_debt"] == pytest.approx(4.0, rel=0.1)
    assert summary["suggested_base_cost"] >= 1.0
    assert summary["suggested_alert"] >= 10.0


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
        collector.track_command("theory", "p1", "g1", True, channel_id="chanA")
        collector.track_command("theory", "p2", "g1", True, channel_id="chanA")
        collector.track_command("expedition", "p1", "g1", True, channel_id="chanB")
        collector.track_command("expedition", "p1", "g1", False, channel_id="chanB")
        collector.flush()

        stats = collector.get_command_stats()

        assert stats["theory"]["usage_count"] == 2
        assert stats["theory"]["success_rate"] == 1.0
        assert stats["theory"]["unique_players"] == 2

        assert stats["expedition"]["usage_count"] == 2
        assert stats["expedition"]["success_rate"] == 0.5
        assert stats["expedition"]["unique_players"] == 1

        usage = collector.get_channel_usage()
        assert usage["chanA"]["usage_count"] == 2
        assert usage["chanA"]["unique_commands"] == 1
        assert usage["chanA"]["unique_players"] == 2
        assert usage["chanB"]["usage_count"] == 2
        assert usage["chanB"]["unique_commands"] == 1
        assert usage["chanB"]["unique_players"] == 1


def test_channel_usage_handles_missing_channel():
    """Channel usage summary should handle missing channel IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "test.db")

        collector.track_command("theory", "p1", "g1", True)
        collector.flush()

        usage = collector.get_channel_usage()
        assert usage["unknown"]["usage_count"] == 1

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


def test_get_economy_metrics_includes_commitments(tmp_path):
    collector = TelemetryCollector(tmp_path / "economy.db")
    collector.track_game_progression(
        "seasonal_commitment_status",
        5.0,
        player_id="p1",
        details={
            "faction": "Academic",
            "tier": "Bronze",
            "remaining_debt": 5,
            "debt_threshold": 8,
            "days_remaining": 2,
            "reprisal_level": 0,
        },
    )
    collector.flush()

    economy = collector.get_economy_metrics(hours=1)
    commitments = economy.get("commitments", {})
    assert commitments.get("total_outstanding") >= 5
    assert "p1" in commitments.get("players", {})


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
        assert "economy" in report
        assert report["overall"]["total_events"] == 4
        assert "health" in report
        assert isinstance(report["health"].get("checks"), list)


def test_economy_metrics_summary():
    """Economy metrics should aggregate investments and endowments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "economy.db")

        collector.track_game_progression(
            "faction_investment",
            5.0,
            player_id="p1",
            details={"faction": "academia", "program": "museum", "total": 5.0},
        )
        collector.track_game_progression(
            "faction_investment",
            3.0,
            player_id="p2",
            details={"faction": "industry", "total": 3.0},
        )
        collector.track_game_progression(
            "archive_endowment",
            4.0,
            player_id="p1",
            details={"faction": "academia", "program": "archive", "paid_debt": 2.0, "reputation_gain": 1.0},
        )
        collector.flush()

        economy = collector.get_economy_metrics(24)
        invest = economy["investments"]
        endow = economy["endowments"]

        assert invest["total_amount"] == pytest.approx(8.0)
        assert invest["unique_players"] == 2
        assert invest["top_share"] == pytest.approx(5.0 / 8.0)
        assert endow["total_amount"] == pytest.approx(4.0)
        assert endow["total_debt_paid"] == pytest.approx(2.0)
        assert endow["total_reputation_gain"] == pytest.approx(1.0)


def test_health_evaluation_thresholds(monkeypatch):
    """Health evaluation should surface alerts when metrics breach thresholds."""
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_DIGEST_MS", "100")
    monkeypatch.setenv("GREAT_WORK_ALERT_MIN_RELEASES", "2")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_QUEUE", "3")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS", "200")
    monkeypatch.setenv("GREAT_WORK_ALERT_LLM_FAILURE_RATE", "0.25")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_ORDER_PENDING", "2")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS", "0.5")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_SYMPOSIUM_DEBT", "1")
    monkeypatch.setenv("GREAT_WORK_ALERT_MAX_SYMPOSIUM_REPRISALS", "0.5")
    monkeypatch.setenv("GREAT_WORK_ALERT_INVESTMENT_SHARE", "0.5")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = TelemetryCollector(Path(tmpdir) / "health.db")

        collector.track_digest(
            duration_ms=250.0,
            release_count=1,
            scheduled_queue_size=5,
        )
        collector.track_queue_depth(5, horizon_hours=48)
        collector.track_queue_depth(2, horizon_hours=24)
        collector.track_llm_activity(
            press_type="expedition",
            success=False,
            duration_ms=250.0,
            error="timeout",
        )
        collector.track_llm_activity(
            press_type="expedition",
            success=True,
            duration_ms=300.0,
        )
        collector.track_order_snapshot(
            order_type="mentorship_activation",
            event="poll",
            pending_count=3,
            oldest_pending_seconds=3600.0,
        )
        collector.track_game_progression(
            "symposium_debt_outstanding",
            5.0,
            player_id="p1",
            details={"faction": "academia"},
        )
        collector.track_game_progression(
            "symposium_debt_reprisal",
            1.0,
            player_id="p1",
            details={"faction": "academia", "reprisal_level": 1},
        )
        collector.track_game_progression(
            "faction_investment",
            10.0,
            player_id="p1",
            details={"faction": "academia", "total": 10.0},
        )
        collector.track_game_progression(
            "faction_investment",
            1.0,
            player_id="p2",
            details={"faction": "industry", "total": 1.0},
        )
        collector.track_game_progression(
            "archive_endowment",
            4.0,
            player_id="p2",
            details={"faction": "industry", "paid_debt": 1.0, "reputation_gain": 1.0},
        )
        collector.flush()

        report = collector.generate_report()
        checks = report["health"]["checks"]

        digest_alert = next(
            (check for check in checks if check["metric"] == "digest_runtime"),
            None,
        )
        assert digest_alert is not None
        assert digest_alert["status"] == "alert"

        release_alert = next(
            (check for check in checks if check["metric"] == "digest_release_floor"),
            None,
        )
        assert release_alert is not None
        assert release_alert["status"] == "alert"

        queue_alert = next(
            (check for check in checks if check["metric"] == "press_queue_depth"),
            None,
        )
        assert queue_alert is not None
        assert queue_alert["status"] == "alert"

        failure_alert = next(
            (check for check in checks if check["metric"] == "llm_failure_rate"),
            None,
        )
        assert failure_alert is not None
        assert failure_alert["status"] == "alert"

        order_pending_alert = next(
            (check for check in checks if check["metric"] == "order_pending"),
            None,
        )
        assert order_pending_alert is not None
        assert order_pending_alert["status"] == "alert"

        order_stale_alert = next(
            (check for check in checks if check["metric"] == "order_staleness"),
            None,
        )
        assert order_stale_alert is not None
        assert order_stale_alert["status"] == "alert"

        symposium_debt_alert = next(
            (check for check in checks if check["metric"] == "symposium_debt"),
            None,
        )
        assert symposium_debt_alert is not None
        assert symposium_debt_alert["status"] == "alert"

        reprisal_alert = next(
            (check for check in checks if check["metric"] == "symposium_reprisal"),
            None,
        )
        assert reprisal_alert is not None
        assert reprisal_alert["status"] == "alert"

        investment_alert = next(
            (check for check in checks if check["metric"] == "investment_concentration"),
            None,
        )
        assert investment_alert is not None
        assert investment_alert["status"] == "alert"


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
