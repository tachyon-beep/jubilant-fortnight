"""Tests for telemetry tooling workflows (KPI thresholds and exports)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from great_work.telemetry import TelemetryCollector
from great_work.tools import generate_sample_telemetry as generate_sample_module
from great_work.tools import export_product_metrics as export_product_metrics_module
from great_work.tools.recommend_kpi_thresholds import (
    apply_thresholds,
    recommend_thresholds,
)


def _build_sample_telemetry(db_path: Path) -> None:
    generate_sample_module.generate(
        telemetry_db=db_path,
        players=4,
        days=5,
        seed=7,
    )


def test_recommend_and_apply_thresholds(tmp_path: Path) -> None:
    """KPI recommendations should be applied into the telemetry DB."""

    db_path = tmp_path / "telemetry.db"
    _build_sample_telemetry(db_path)

    recommendations = recommend_thresholds(
        db_path,
        engagement_days=7,
        manifesto_days=7,
        archive_days=7,
    )

    assert recommendations
    collector = TelemetryCollector(db_path)
    applied = apply_thresholds(collector, recommendations)

    targets = collector.get_kpi_targets()
    for metric_key in applied:
        assert metric_key in targets
        assert targets[metric_key]["target"] == applied[metric_key]["target"]


def test_export_product_metrics_outputs(tmp_path: Path) -> None:
    """Exporter should generate JSON and CSV payloads in the target directory."""

    db_path = tmp_path / "telemetry.db"
    _build_sample_telemetry(db_path)

    output_dir = tmp_path / "exports"
    exports = export_product_metrics_module.export_metrics(
        db_path,
        output_dir=output_dir,
    )

    json_path = exports["json"]
    csv_path = exports["csv"]

    assert json_path.exists()
    payload = json.loads(json_path.read_text())
    assert "product_kpis" in payload
    assert "product_kpi_history" in payload
    assert "engagement_cohorts" in payload

    assert csv_path.exists()
    csv_lines = csv_path.read_text().strip().splitlines()
    # Header + at least one history row
    assert len(csv_lines) >= 2
