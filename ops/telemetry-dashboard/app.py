"""Containerised telemetry dashboard for The Great Work."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
    context = {
        "report": report,
        "command_stats_sorted": command_stats_sorted,
        "press_cadence": press_cadence,
        "llm_activity": llm_activity,
    }
    return context


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
