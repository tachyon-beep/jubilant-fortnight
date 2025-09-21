"""Tests for deployment smoke checks."""

from __future__ import annotations

from great_work.tools import deployment_smoke


def test_smoke_checks_missing_required_env():
    env = {}
    results = deployment_smoke.run_checks(env)
    statuses = {result.name: result.status for result in results}
    assert statuses["DISCORD_TOKEN"] == "error"
    assert statuses["discord_channels"] == "warning"


def test_smoke_checks_all_good():
    env = {
        "DISCORD_TOKEN": "abc",
        "DISCORD_APP_ID": "123",
        "GREAT_WORK_CHANNEL_TABLE_TALK": "999",
        "GREAT_WORK_GUARDIAN_MODE": "sidecar",
        "GREAT_WORK_GUARDIAN_URL": "http://localhost:8085/score",
        "GREAT_WORK_ALERT_WEBHOOK_URLS": "https://ops/webhook",
    }
    results = deployment_smoke.run_checks(env)
    assert all(
        result.status == "ok" for result in results if result.name != "alert_routing"
    )
    assert any(
        result.name == "alert_routing" and result.status == "ok" for result in results
    )
