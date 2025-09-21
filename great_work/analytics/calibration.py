"""Calibration snapshot helpers for telemetry tuning and economy balance."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..service import GameService
from ..telemetry import TelemetryCollector


def collect_calibration_snapshot(
    service: GameService,
    telemetry: TelemetryCollector,
    *,
    now: Optional[datetime] = None,
    include_details: bool = True,
) -> Dict[str, Any]:
    """Build a structured snapshot for post-digest calibration workflows."""

    current_time = now or datetime.now(timezone.utc)
    state = service.state
    settings = service.settings

    snapshot: Dict[str, Any] = {
        "generated_at": _iso(current_time),
        "seasonal_commitments": _seasonal_commitment_summary(
            service, current_time, include_details
        ),
        "faction_investments": _investment_summary(
            state.list_faction_investments(), include_details
        ),
        "archive_endowments": _endowment_summary(
            state.list_archive_endowments(), include_details
        ),
        "symposium": service.symposium_backlog_report(),
        "orders": _orders_summary(state.list_orders(status="pending"), include_details),
        "telemetry": {
            "product_kpis": telemetry.get_product_kpis(),
            "kpi_targets": telemetry.get_kpi_targets(),
            "kpi_history": telemetry.get_product_kpi_history_summary(),
            "engagement_cohorts": telemetry.get_engagement_cohorts(),
        },
        "settings": {
            "seasonal_commitment": {
                "base_cost": settings.seasonal_commitment_base_cost,
                "duration_days": settings.seasonal_commitment_duration_days,
                "relationship_weight": settings.seasonal_commitment_relationship_weight,
                "min_relationship": settings.seasonal_commitment_min_relationship,
                "reprisal_threshold": settings.seasonal_commitment_reprisal_threshold,
                "reprisal_penalty": settings.seasonal_commitment_reprisal_penalty,
                "reprisal_cooldown_days": settings.seasonal_commitment_reprisal_cooldown_days,
            },
            "symposium": {
                "max_backlog": settings.symposium_max_backlog,
                "max_per_player": settings.symposium_max_per_player,
                "recent_window": settings.symposium_recent_window,
                "scoring": {
                    "age_weight": settings.symposium_scoring_age_weight,
                    "fresh_bonus": settings.symposium_scoring_fresh_bonus,
                    "repeat_penalty": settings.symposium_scoring_repeat_penalty,
                    "max_age_days": settings.symposium_scoring_max_age_days,
                },
                "debt_reprisal_threshold": settings.symposium_debt_reprisal_threshold,
                "debt_reprisal_penalty": settings.symposium_debt_reprisal_penalty,
                "debt_cooldown_days": settings.symposium_debt_reprisal_cooldown_days,
            },
            "influence_sinks": {
                "faction_investment_min": settings.faction_investment_min_amount,
                "faction_investment_bonus": settings.faction_investment_feeling_bonus,
                "archive_endowment_min": settings.archive_endowment_min_amount,
                "archive_endowment_reputation_threshold": settings.archive_endowment_reputation_threshold,
                "archive_endowment_reputation_bonus": settings.archive_endowment_reputation_bonus,
            },
        },
    }

    return snapshot


def write_calibration_snapshot(
    service: GameService,
    telemetry: TelemetryCollector,
    output_dir: Path,
    *,
    now: Optional[datetime] = None,
    include_details: bool = True,
    keep_last: int = 0,
    snapshot: Optional[Dict[str, Any]] = None,
) -> Path:
    """Render the current calibration snapshot to the requested directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    current_time = now or datetime.now(timezone.utc)
    snapshot = snapshot or collect_calibration_snapshot(
        service,
        telemetry,
        now=current_time,
        include_details=include_details,
    )

    timestamp = current_time.strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"calibration_snapshot_{timestamp}.json"
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    latest_path = output_dir / "latest.json"
    latest_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    if keep_last > 0:
        _prune_snapshots(output_dir, keep_last)

    return output_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _seasonal_commitment_summary(
    service: GameService,
    now: datetime,
    include_details: bool,
) -> Dict[str, Any]:
    state = service.state
    settings = service.settings
    commitments = state.list_active_seasonal_commitments(now)

    per_faction: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"commitments": 0, "base_cost_total": 0, "outstanding_debt": 0}
    )
    per_tier: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"commitments": 0, "base_cost_total": 0, "outstanding_debt": 0}
    )

    records: list[Dict[str, Any]] = []
    total_base = 0
    total_debt = 0

    for commitment in commitments:
        faction = commitment.get("faction") or "unaligned"
        tier = commitment.get("tier") or "default"
        base_cost = int(commitment.get("base_cost", 0) or 0)
        debt_record = state.get_influence_debt_record(
            player_id=commitment["player_id"],
            faction=faction,
            source="seasonal",
        )
        outstanding = int(debt_record.get("amount", 0)) if debt_record else 0
        total_base += base_cost
        total_debt += outstanding

        bucket_faction = per_faction[faction]
        bucket_faction["commitments"] += 1
        bucket_faction["base_cost_total"] += base_cost
        bucket_faction["outstanding_debt"] += outstanding

        bucket_tier = per_tier[tier]
        bucket_tier["commitments"] += 1
        bucket_tier["base_cost_total"] += base_cost
        bucket_tier["outstanding_debt"] += outstanding

        if include_details:
            records.append(
                {
                    "id": commitment.get("id"),
                    "player_id": commitment.get("player_id"),
                    "faction": faction,
                    "tier": tier,
                    "base_cost": base_cost,
                    "start_at": _iso(commitment.get("start_at")),
                    "end_at": _iso(commitment.get("end_at")),
                    "status": commitment.get("status"),
                    "last_processed_at": _iso(commitment.get("last_processed_at")),
                    "updated_at": _iso(commitment.get("updated_at")),
                    "outstanding_debt": outstanding,
                    "reprisal_level": int(debt_record.get("reprisal_level", 0))
                    if debt_record
                    else 0,
                    "last_reprisal_at": _iso(
                        debt_record.get("last_reprisal_at") if debt_record else None
                    ),
                }
            )

    summary: Dict[str, Any] = {
        "totals": {
            "active": len(commitments),
            "base_cost_total": total_base,
            "outstanding_debt": total_debt,
            "per_faction": _as_serialisable_dict(per_faction),
            "per_tier": _as_serialisable_dict(per_tier),
        },
        "config": {
            "relationship_weight": settings.seasonal_commitment_relationship_weight,
            "reprisal_threshold": settings.seasonal_commitment_reprisal_threshold,
            "reprisal_penalty": settings.seasonal_commitment_reprisal_penalty,
            "reprisal_cooldown_days": settings.seasonal_commitment_reprisal_cooldown_days,
        },
    }

    if include_details:
        summary["commitments"] = records

    return summary


def _investment_summary(
    investments: Iterable[Dict[str, Any]],
    include_details: bool,
) -> Dict[str, Any]:
    per_faction: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": 0}
    )
    per_program: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": 0}
    )
    per_player: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": 0}
    )
    rows: list[Dict[str, Any]] = []
    total_amount = 0

    for entry in investments:
        faction = entry.get("faction") or "unaligned"
        program = entry.get("program") or "general"
        player_id = entry.get("player_id") or "unknown"
        amount = int(entry.get("amount", 0) or 0)
        total_amount += amount

        per_faction[faction]["count"] += 1
        per_faction[faction]["amount"] += amount

        per_program[program]["count"] += 1
        per_program[program]["amount"] += amount

        per_player[player_id]["count"] += 1
        per_player[player_id]["amount"] += amount

        if include_details:
            rows.append(
                {
                    "id": entry.get("id"),
                    "player_id": player_id,
                    "faction": faction,
                    "program": program,
                    "amount": amount,
                    "created_at": _iso(entry.get("created_at")),
                }
            )

    summary: Dict[str, Any] = {
        "totals": {
            "count": sum(bucket["count"] for bucket in per_faction.values()),
            "amount": total_amount,
            "per_faction": _as_serialisable_dict(per_faction),
            "per_program": _as_serialisable_dict(per_program),
            "per_player": _as_serialisable_dict(per_player),
        }
    }
    if include_details:
        summary["investments"] = rows
    return summary


def _endowment_summary(
    endowments: Iterable[Dict[str, Any]],
    include_details: bool,
) -> Dict[str, Any]:
    per_program: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": 0}
    )
    per_player: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "amount": 0}
    )
    rows: list[Dict[str, Any]] = []
    total_amount = 0

    for entry in endowments:
        program = entry.get("program") or "general"
        player_id = entry.get("player_id") or "unknown"
        amount = int(entry.get("amount", 0) or 0)
        total_amount += amount

        per_program[program]["count"] += 1
        per_program[program]["amount"] += amount

        per_player[player_id]["count"] += 1
        per_player[player_id]["amount"] += amount

        if include_details:
            rows.append(
                {
                    "id": entry.get("id"),
                    "player_id": player_id,
                    "program": program,
                    "amount": amount,
                    "created_at": _iso(entry.get("created_at")),
                }
            )

    summary: Dict[str, Any] = {
        "totals": {
            "count": sum(bucket["count"] for bucket in per_program.values()),
            "amount": total_amount,
            "per_program": _as_serialisable_dict(per_program),
            "per_player": _as_serialisable_dict(per_player),
        }
    }
    if include_details:
        summary["endowments"] = rows
    return summary


def _orders_summary(
    orders: Iterable[Dict[str, Any]],
    include_details: bool,
) -> Dict[str, Any]:
    per_type: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "oldest": None}
    )
    records: list[Dict[str, Any]] = []
    total = 0

    for order in orders:
        order_type = order.get("order_type") or "unknown"
        bucket = per_type[order_type]
        bucket["count"] += 1
        total += 1

        scheduled_at = order.get("scheduled_at")
        created_at = order.get("created_at")
        timestamp = scheduled_at or created_at
        iso_ts = _iso(timestamp)
        if iso_ts is not None:
            previous = bucket.get("oldest")
            if previous is None or iso_ts < previous:
                bucket["oldest"] = iso_ts

        if include_details:
            records.append(
                {
                    "id": order.get("id"),
                    "order_type": order_type,
                    "actor_id": order.get("actor_id"),
                    "subject_id": order.get("subject_id"),
                    "status": order.get("status"),
                    "scheduled_at": _iso(scheduled_at),
                    "created_at": _iso(created_at),
                    "updated_at": _iso(order.get("updated_at")),
                    "payload": order.get("payload"),
                }
            )

    summary: Dict[str, Any] = {
        "totals": {
            "pending": total,
            "per_type": _as_serialisable_dict(per_type),
        }
    }
    if include_details:
        summary["orders"] = records
    return summary


def _prune_snapshots(target_dir: Path, keep_last: int) -> None:
    snapshots = sorted(
        [path for path in target_dir.glob("calibration_snapshot_*.json") if path.is_file()]
    )
    if len(snapshots) <= keep_last:
        return
    for path in snapshots[: -keep_last]:
        try:
            path.unlink()
        except OSError:
            continue


def _iso(value: Optional[datetime]) -> Optional[str]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return None


def _as_serialisable_dict(mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in mapping.items()}
