"""Management utilities for dispatcher orders and follow-up migration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..state import GameState


def _load_state(state_db: Path) -> GameState:
    settings = get_settings()
    return GameState(state_db, start_year=settings.timeline_start_year)


def _orders_summary(state: GameState, order_type: Optional[str], status: Optional[str]) -> Dict[str, Any]:
    orders = state.list_orders()
    if order_type:
        orders = [order for order in orders if order.get("order_type") == order_type]
    if status:
        orders = [order for order in orders if order.get("status") == status]

    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for order in orders:
        order_name = order.get("order_type", "unknown")
        by_type[order_name] = by_type.get(order_name, 0) + 1
        order_status = order.get("status", "unknown")
        by_status[order_status] = by_status.get(order_status, 0) + 1

    return {
        "total": len(orders),
        "by_type": by_type,
        "by_status": by_status,
        "orders": orders,
    }


def cmd_summary(args: argparse.Namespace) -> None:
    state = _load_state(args.state_db)
    summary = _orders_summary(state, args.order_type, args.status)
    if args.json:
        print(json.dumps(summary, default=str, indent=2))
        return

    lines: List[str] = []
    lines.append(f"Total orders: {summary['total']}")
    if summary["by_type"]:
        lines.append("By type:")
        for name, count in sorted(summary["by_type"].items()):
            lines.append(f"  - {name}: {count}")
    if summary["by_status"]:
        lines.append("By status:")
        for name, count in sorted(summary["by_status"].items()):
            lines.append(f"  - {name}: {count}")

    print("\n".join(lines))


def cmd_followups(args: argparse.Namespace) -> None:
    state = _load_state(args.state_db)
    if args.action == "preview":
        summary = state.preview_followup_migration()
        summary["migrated"] = False
    else:
        summary = state.migrate_followups(dry_run=args.dry_run)

    if args.json or args.dry_run:
        print(json.dumps(summary, indent=2))
        return

    migrated_rows = summary.get("migrated_rows", 0)
    pending_rows = summary.get("pending_rows", 0)
    print(
        f"Follow-up migration summary: {pending_rows} rows pending, migrated {migrated_rows}."
    )
    kinds = summary.get("kinds", {})
    if kinds:
        print("Kinds:")
        for name, count in sorted(kinds.items()):
            print(f"  - {name}: {count}")
    existing = summary.get("existing_orders", {})
    if existing:
        print("Existing follow-up orders:")
        by_status = existing.get("by_status", {})
        if by_status:
            for name, count in sorted(by_status.items()):
                print(f"  - status {name}: {count}")
        by_kind = existing.get("by_kind", {})
        if by_kind:
            for name, count in sorted(by_kind.items()):
                print(f"  - kind {name}: {count}")
        if existing.get("oldest"):
            print(f"  Oldest pending: {existing['oldest']}")
        if existing.get("newest"):
            print(f"  Most recent: {existing['newest']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage dispatcher orders and follow-up migration.")
    parser.add_argument(
        "--state-db",
        type=Path,
        default=Path("great_work.db"),
        help="Path to the game state SQLite database (default: great_work.db).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="Summarise current dispatcher orders.")
    summary.add_argument("--order-type", type=str, help="Filter by order type.")
    summary.add_argument("--status", type=str, help="Filter by order status.")
    summary.add_argument("--json", action="store_true", help="Output JSON for automation.")
    summary.set_defaults(func=cmd_summary)

    followups = subparsers.add_parser(
        "followups",
        help="Preview or migrate legacy follow-up rows into the dispatcher.",
    )
    followups.add_argument(
        "action",
        choices=["preview", "migrate"],
        help="Choose whether to preview or execute the migration.",
    )
    followups.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the migration logic without writing changes (implies JSON output).",
    )
    followups.add_argument("--json", action="store_true", help="Emit JSON output.")
    followups.set_defaults(func=cmd_followups)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
