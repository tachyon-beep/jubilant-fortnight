"""Tests for telemetry dashboard API endpoints."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
import sys

import pytest

try:  # pragma: no cover - optional dependency in minimal test environments
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    pytest.skip("fastapi not installed", allow_module_level=True)


def load_dashboard_module(tmp_path: Path):
    """Load the dashboard module with a temporary telemetry database."""

    spec = importlib.util.spec_from_file_location(
        "telemetry_dashboard_app",
        Path("ops") / "telemetry-dashboard" / "app.py",
    )
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)  # type: ignore[assignment]
    return module


@pytest.fixture
def dashboard_module(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "dashboard.db"
        monkeypatch.setenv("TELEMETRY_DB_PATH", str(db_path))
        module = load_dashboard_module(tmp_path)
        yield module
        sys.modules.pop("telemetry_dashboard_app", None)


def test_orders_api_returns_filtered_records(dashboard_module):
    collector = dashboard_module.collector
    collector.track_order_snapshot(
        order_type="mentorship_activation",
        event="poll",
        pending_count=4,
        oldest_pending_seconds=7200.0,
    )
    collector.track_order_snapshot(
        order_type="conference_resolution",
        event="poll",
        pending_count=2,
        oldest_pending_seconds=1800.0,
    )
    collector.flush()

    client = TestClient(dashboard_module.app)
    response = client.get("/api/orders", params={"order_type": "mentorship_activation", "hours": 24})
    assert response.status_code == 200
    payload = response.json()
    assert payload["records"]
    assert all(record["order_type"] == "mentorship_activation" for record in payload["records"])

    csv_response = client.get("/api/orders.csv", params={"hours": 24, "limit": 10})
    assert csv_response.status_code == 200
    body = csv_response.text.strip().splitlines()
    assert body[0] == "order_type,pending,oldest_pending_seconds,event,timestamp"
