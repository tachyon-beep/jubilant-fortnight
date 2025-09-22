"""Dispatcher orders helpers for admin flows."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def summarize_orders(
    orders: List[Dict[str, Any]], *, limit: int
) -> List[Dict[str, object]]:
    """Trim and summarize orders for admin listing."""

    limit = max(1, min(limit, 50))
    trimmed = orders[:limit]
    summaries: List[Dict[str, object]] = []
    for order in trimmed:
        summaries.append(
            {
                "id": order["id"],
                "order_type": order.get("order_type"),
                "status": order.get("status"),
                "actor_id": order.get("actor_id"),
                "subject_id": order.get("subject_id"),
                "scheduled_at": (
                    order.get("scheduled_at").isoformat()
                    if isinstance(order.get("scheduled_at"), datetime)
                    else None
                ),
                "created_at": (
                    order.get("created_at").isoformat()
                    if isinstance(order.get("created_at"), datetime)
                    else None
                ),
                "payload": order.get("payload", {}),
            }
        )
    return summaries


def cancellation_summary(order: Dict[str, Any], *, order_id: int, reason: str | None) -> Dict[str, object]:
    """Build a summary dict after cancellation."""

    return {
        "id": order_id,
        "order_type": order.get("order_type"),
        "actor_id": order.get("actor_id"),
        "subject_id": order.get("subject_id"),
        "reason": reason,
    }


def cancellation_notice(summary: Dict[str, object]) -> str:
    """Human-readable cancellation notice for admin channel."""

    text = f"🧾 Cancelled order #{summary['id']} ({summary.get('order_type')})"
    if summary.get("reason"):
        text += f" – {summary['reason']}"
    return text


__all__ = [
    "summarize_orders",
    "cancellation_summary",
    "cancellation_notice",
]

