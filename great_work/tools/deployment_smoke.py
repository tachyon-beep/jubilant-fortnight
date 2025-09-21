"""Deployment smoke checks for The Great Work."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, replace
from typing import Iterable, List, Mapping


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


REQUIRED_ENV = ["DISCORD_TOKEN", "DISCORD_APP_ID"]
CHANNEL_VARS = [
    "GREAT_WORK_CHANNEL_TABLE_TALK",
    "GREAT_WORK_CHANNEL_GAZETTE",
    "GREAT_WORK_CHANNEL_UPCOMING",
    "GREAT_WORK_CHANNEL_ORDERS",
]


def _status(level: str, name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status=level, detail=detail)


def run_checks(env: Mapping[str, str]) -> List[CheckResult]:
    results: List[CheckResult] = []

    for key in REQUIRED_ENV:
        if env.get(key):
            results.append(_status("ok", key, "present"))
        else:
            results.append(_status("error", key, "missing"))

    if any(env.get(var) for var in CHANNEL_VARS):
        results.append(_status("ok", "discord_channels", "at least one channel configured"))
    else:
        results.append(
            _status(
                "warning",
                "discord_channels",
                "no public channel variables configured; informational commands will not broadcast",
            )
        )

    guardian_mode = env.get("GREAT_WORK_GUARDIAN_MODE", "sidecar").lower()
    if guardian_mode == "sidecar":
        if env.get("GREAT_WORK_GUARDIAN_URL"):
            results.append(_status("ok", "guardian_url", "sidecar endpoint configured"))
        else:
            severity = "warning" if env.get("GREAT_WORK_MODERATION_STRICT", "true").lower() in {"false", "0", "off"} else "error"
            detail = "Guardian sidecar URL missing; prefiler-only mode" if severity == "warning" else "Guardian sidecar URL missing while strict mode enabled"
            results.append(_status(severity, "guardian_url", detail))
    elif guardian_mode == "local":
        if env.get("GREAT_WORK_GUARDIAN_LOCAL_PATH"):
            results.append(_status("ok", "guardian_local_path", "local weights configured"))
        else:
            results.append(_status("warning", "guardian_local_path", "local mode without path; default weights assumed"))

    webhook_urls = env.get("GREAT_WORK_ALERT_WEBHOOK_URLS", "").strip()
    webhook_url = env.get("GREAT_WORK_ALERT_WEBHOOK_URL", "").strip()
    email_to = env.get("GREAT_WORK_ALERT_EMAIL_TO", "").strip()
    if webhook_urls or webhook_url or email_to:
        results.append(_status("ok", "alert_routing", "alerts fan out to at least one destination"))
    else:
        results.append(_status("warning", "alert_routing", "no webhook/email configured; alerts will log locally only"))

    return results


def _print_table(results: Iterable[CheckResult]) -> None:
    header = f"{'Check':<32} {'Status':<8} Detail"
    print(header)
    print("-" * len(header))
    for result in results:
        print(f"{result.name:<32} {result.status:<8} {result.detail}")


def main(argv: Iterable[str] | None = None) -> int:  # pragma: no cover - CLI entry point
    parser = argparse.ArgumentParser(description="Run deployment smoke checks for The Great Work.")
    parser.parse_args(argv)
    results = run_checks(os.environ)
    _print_table(results)
    if any(result.status == "error" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

