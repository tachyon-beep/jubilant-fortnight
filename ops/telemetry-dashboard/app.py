"""Containerised telemetry dashboard for The Great Work."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from great_work.telemetry import TelemetryCollector

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
DEFAULT_DB_PATH = Path(os.environ.get("TELEMETRY_DB_PATH", "/data/telemetry.db"))

collector = TelemetryCollector(DEFAULT_DB_PATH)

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

app = FastAPI(title="The Great Work Telemetry Dashboard")


MAX_QUERY_HOURS = int(os.environ.get("TELEMETRY_MAX_QUERY_HOURS", "168") or 168)
MAX_ORDER_RECORDS = int(os.environ.get("TELEMETRY_MAX_ORDER_RECORDS", "1000") or 1000)


def build_report() -> dict:
    """Fetch the latest aggregated telemetry report."""

    collector.flush()
    return collector.generate_report()


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
        "order_types": order_types,
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
async def api_order_records(order_type: Optional[str] = None, hours: int = 24, limit: int = 250) -> JSONResponse:
    """Return dispatcher backlog events with optional filtering."""

    normalised_hours = _normalise_hours(hours)
    normalised_limit = _normalise_limit(limit)

    records = collector.get_order_backlog_events(
        order_type=order_type or None,
        hours=normalised_hours,
        limit=normalised_limit,
    )
    order_types = sorted(collector.get_order_backlog_summary(MAX_QUERY_HOURS).keys())
    payload = {
        "order_type": order_type,
        "hours": normalised_hours,
        "limit": normalised_limit,
        "records": records,
        "order_types": order_types,
    }
    return JSONResponse(payload)


@app.get("/api/orders.csv")
async def api_order_records_csv(order_type: Optional[str] = None, hours: int = 24, limit: int = 250) -> StreamingResponse:
    """Export dispatcher backlog events as CSV."""

    normalised_hours = _normalise_hours(hours)
    normalised_limit = _normalise_limit(limit)

    records = collector.get_order_backlog_events(
        order_type=order_type or None,
        hours=normalised_hours,
        limit=normalised_limit,
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
