"""Containerised telemetry dashboard for The Great Work."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from . import qdrant_helpers

from great_work.telemetry import TelemetryCollector

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
DEFAULT_DB_PATH = Path(os.environ.get("TELEMETRY_DB_PATH", "/data/telemetry.db"))
CALIBRATION_DIR = Path(os.environ.get("CALIBRATION_SNAPSHOT_DIR", "/data/calibration_snapshots"))

collector = TelemetryCollector(DEFAULT_DB_PATH)

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

app = FastAPI(title="The Great Work Telemetry Dashboard")


class SemanticPressResult(BaseModel):
    id: Optional[str]
    headline: str
    excerpt: str
    score: Optional[float] = None
    timestamp: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


MAX_QUERY_HOURS = int(os.environ.get("TELEMETRY_MAX_QUERY_HOURS", "168") or 168)
MAX_ORDER_RECORDS = int(os.environ.get("TELEMETRY_MAX_ORDER_RECORDS", "1000") or 1000)
MAX_HISTORY_DAYS = int(os.environ.get("TELEMETRY_MAX_HISTORY_DAYS", "120") or 120)


def build_report() -> dict:
    """Fetch the latest aggregated telemetry report."""

    collector.flush()
    return collector.generate_report()


def _load_latest_calibration_snapshot() -> Optional[dict]:
    """Return the most recent calibration snapshot if available."""

    if not CALIBRATION_DIR:
        return None
    latest_path = CALIBRATION_DIR / "latest.json"
    if not latest_path.exists():
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):  # pragma: no cover - defensive
        return None


def build_context(report: dict) -> dict:
    """Prepare sorted slices for template rendering."""

    command_stats_sorted = sorted(
        report.get("command_stats", {}).items(),
        key=lambda item: item[1]["usage_count"],
        reverse=True,
    )
    press_cadence = report.get("press_cadence_24h", [])
    llm_activity = sorted(
        report.get("llm_activity_24h", {}).items(),
        key=lambda item: item[1]["total_calls"],
        reverse=True,
    )
    queue_depth = sorted(
        report.get("queue_depth_24h", {}).items(),
        key=lambda item: int(item[0]),
    )
    order_backlog = sorted(
        report.get("order_backlog_24h", {}).items(),
        key=lambda item: item[1].get("latest_pending", 0.0),
        reverse=True,
    )
    order_types = [name for name, _ in order_backlog]
    health = report.get("health", {})
    health_checks = health.get("checks", [])
    symposium = report.get("symposium", {})
    symposium_scoring = symposium.get("scoring", {})
    scoring_top = symposium_scoring.get("top", [])
    symposium_debts = symposium.get("debts", [])
    symposium_reprisal = symposium.get("reprisals", [])
    symposium_participation = symposium.get("participation", {})
    product_kpis = report.get("product_kpis", {})
    engagement = product_kpis.get("engagement", {})
    manifestos = product_kpis.get("manifestos", {})
    archive = product_kpis.get("archive", {})
    nicknames = product_kpis.get("nicknames", {})
    shares = product_kpis.get("press_shares", {})
    product_history = report.get("product_kpi_history", {})
    history_summary = product_history.get("summary", {})
    engagement_cohorts = report.get("engagement_cohorts", {})
    kpi_targets = report.get("kpi_targets", {})
    calibration_snapshot = None
    raw_snapshot = _load_latest_calibration_snapshot()
    if raw_snapshot:
        seasonal_totals = raw_snapshot.get("seasonal_commitments", {}).get("totals", {})
        investment_totals = raw_snapshot.get("faction_investments", {}).get("totals", {})
        endowment_totals = raw_snapshot.get("archive_endowments", {}).get("totals", {})
        order_totals = raw_snapshot.get("orders", {}).get("totals", {})
        calibration_snapshot = {
            "generated_at": raw_snapshot.get("generated_at"),
            "seasonal_active": seasonal_totals.get("active", 0),
            "seasonal_debt": seasonal_totals.get("outstanding_debt", 0),
            "investment_amount": investment_totals.get("amount", 0),
            "endowment_amount": endowment_totals.get("amount", 0),
            "orders_pending": order_totals.get("pending", 0),
        }

    qdrant_status = qdrant_helpers.get_status()
    context = {
        "report": report,
        "command_stats_sorted": command_stats_sorted,
        "press_cadence": press_cadence,
        "llm_activity": llm_activity,
        "queue_depth": queue_depth,
        "order_backlog": order_backlog,
        "health_checks": health_checks,
        "health_thresholds": health.get("thresholds", {}),
        "symposium_scoring": symposium_scoring,
        "symposium_scoring_top": scoring_top,
        "symposium_debts": symposium_debts,
        "symposium_reprisal": symposium_reprisal,
        "symposium_participation": symposium_participation,
        "order_types": order_types,
        "product_engagement": engagement,
        "product_manifestos": manifestos,
        "product_archive": archive,
        "product_nicknames": nicknames,
        "product_shares": shares,
        "product_history": product_history.get("daily", []),
        "product_history_window": product_history.get("window_days", 0),
        "product_history_summary": history_summary,
        "engagement_cohorts": engagement_cohorts,
        "kpi_targets": kpi_targets,
        "calibration_snapshot": calibration_snapshot,
        "qdrant_search_enabled": qdrant_status[0],
        "qdrant_search_error": qdrant_status[1],
    }
    return context


def _normalise_hours(value: int) -> int:
    if value <= 0:
        raise HTTPException(status_code=400, detail="hours must be positive")
    return min(value, MAX_QUERY_HOURS)


def _normalise_limit(value: int) -> int:
    if value <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")
    return min(value, MAX_ORDER_RECORDS)


def _normalise_days(value: int) -> int:
    if value <= 0:
        raise HTTPException(status_code=400, detail="days must be positive")
    return min(value, MAX_HISTORY_DAYS)

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Render the dashboard landing page."""

    report = build_report()
    template = jinja_env.get_template("index.html")
    context = build_context(report)
    html = template.render(**context)
    return HTMLResponse(html)


@app.get("/health", response_class=HTMLResponse)
async def healthcheck() -> HTMLResponse:
    """Simple health endpoint for container orchestration."""

    if DEFAULT_DB_PATH.exists():
        status = "ok"
    else:
        status = "telemetry database not found"
    return HTMLResponse(f"telemetry-dashboard: {status}")


@app.get("/api/orders", response_class=JSONResponse)
async def api_order_records(
    order_type: Optional[str] = None,
    hours: int = 24,
    limit: int = 250,
    event: Optional[str] = None,
    min_pending: Optional[float] = None,
    min_age_hours: Optional[float] = None,
) -> JSONResponse:
    """Return dispatcher backlog events with optional filtering."""

    normalised_hours = _normalise_hours(hours)
    normalised_limit = _normalise_limit(limit)
    min_age_seconds = None
    if min_age_hours is not None:
        if min_age_hours < 0:
            raise HTTPException(status_code=400, detail="min_age_hours must be non-negative")
        min_age_seconds = float(min_age_hours) * 3600.0

    records = collector.get_order_backlog_events(
        order_type=order_type or None,
        hours=normalised_hours,
        limit=normalised_limit,
        event=event or None,
        min_pending=min_pending,
        min_age_seconds=min_age_seconds,
    )
    order_types = sorted(collector.get_order_backlog_summary(MAX_QUERY_HOURS).keys())
    payload = {
        "order_type": order_type,
        "hours": normalised_hours,
        "limit": normalised_limit,
        "event": event,
        "min_pending": min_pending,
        "min_age_hours": min_age_hours,
        "records": records,
        "order_types": order_types,
    }
    return JSONResponse(payload)


@app.get("/api/semantic-press", response_model=list[SemanticPressResult])
async def api_semantic_press(
    query: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(5, ge=1, le=10),
) -> list[SemanticPressResult]:
    """Semantic press search backed by Qdrant embeddings."""

    enabled, error = qdrant_helpers.get_status()
    if not enabled:
        raise HTTPException(status_code=503, detail=error or "Semantic search disabled")

    try:
        results = qdrant_helpers.search_press(query, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to client
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [SemanticPressResult(**item) for item in results]


@app.get("/api/orders.csv")
async def api_order_records_csv(
    order_type: Optional[str] = None,
    hours: int = 24,
    limit: int = 250,
    event: Optional[str] = None,
    min_pending: Optional[float] = None,
    min_age_hours: Optional[float] = None,
) -> StreamingResponse:
    """Export dispatcher backlog events as CSV."""

    normalised_hours = _normalise_hours(hours)
    normalised_limit = _normalise_limit(limit)
    min_age_seconds = None
    if min_age_hours is not None:
        if min_age_hours < 0:
            raise HTTPException(status_code=400, detail="min_age_hours must be non-negative")
        min_age_seconds = float(min_age_hours) * 3600.0

    records = collector.get_order_backlog_events(
        order_type=order_type or None,
        hours=normalised_hours,
        limit=normalised_limit,
        event=event or None,
        min_pending=min_pending,
        min_age_seconds=min_age_seconds,
    )

    def _row_iter() -> Iterable[str]:
        yield "order_type,pending,oldest_pending_seconds,event,timestamp\n"
        for record in records:
            oldest = record["oldest_pending_seconds"]
            oldest_val = f"{oldest:.0f}" if oldest is not None else ""
            row = ",".join(
                [
                    record["order_type"],
                    f"{record['pending']:.0f}",
                    oldest_val,
                    record.get("event", ""),
                    record["timestamp"],
                ]
            )
            yield row + "\n"

    filename = "order_backlog.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(_row_iter(), media_type="text/csv", headers=headers)


@app.get("/api/kpi_history", response_class=JSONResponse)
async def api_kpi_history(days: int = 30) -> JSONResponse:
    """Return KPI history in JSON for charts."""

    normalised_days = _normalise_days(days)
    history = collector.get_product_kpi_history_summary(days=normalised_days)
    return JSONResponse({
        "window_days": history.get("window_days", normalised_days),
        "daily": history.get("daily", []),
        "summary": history.get("summary", {}),
    })


@app.get("/api/calibration_snapshot", response_class=JSONResponse)
async def api_calibration_snapshot() -> JSONResponse:
    """Expose the most recent calibration snapshot for automation."""

    snapshot = _load_latest_calibration_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="calibration snapshot not available")
    return JSONResponse(snapshot)
