"""Symposium formatting helpers."""

from __future__ import annotations

from typing import Dict, List, Tuple


def compute_winner(votes: Dict[int, int] | None) -> Tuple[str, str]:
    """Compute the winning option and a human-readable summary.

    Returns (winner, winner_text) where winner is one of "1", "2", "3" or "none".
    """

    if not votes:
        return "none", "No consensus (no votes received)"

    winner_option = max(votes.keys(), key=lambda x: votes.get(x, 0))
    winner_count = votes[winner_option]
    total_votes = sum(votes.values())
    winner_text = {
        1: f"The proposition is supported ({winner_count}/{total_votes} votes)",
        2: f"The proposition is opposed ({winner_count}/{total_votes} votes)",
        3: f"Further study is required ({winner_count}/{total_votes} votes)",
    }[winner_option]
    return str(winner_option), winner_text


def build_announcement_body(
    *,
    topic: str,
    description: str,
    proposer_display: str | None,
    pledge_base: int,
    pledge_cap: int,
    grace_misses: int,
    grace_window_days: int,
) -> List[str]:
    lines = [
        f"The Academy announces this week's symposium topic: {topic}",
        "",
        description,
        "",
        "Cast your votes with /symposium_vote:",
        "Option 1: Support the proposition",
        "Option 2: Oppose the proposition",
        "Option 3: Call for further study",
        "",
        (
            f"Silent scholars risk forfeiting {pledge_base} influence plus 1 per consecutive miss "
            f"(up to {pledge_base + pledge_cap})."
        ),
        (
            f"Everyone receives {grace_misses} grace miss per {grace_window_days}-day window; "
            "voting refreshes your grace."
        ),
    ]
    if proposer_display:
        lines.insert(1, f"Proposed by {proposer_display}.")
    return lines


def build_resolution_body(
    *, topic: str, winner_text: str, non_voters: List[str], penalty_records: List[Dict[str, object]]
) -> List[str]:
    lines: List[str] = [
        f"The symposium on '{topic}' has concluded.",
        "",
        f"Result: {winner_text}",
        "",
        "The Academy thanks all participants for their thoughtful contributions.",
    ]
    if non_voters:
        lines.append("")
        lines.append("Outstanding responses required from: " + ", ".join(non_voters))
    if penalty_records:
        lines.append("")
        lines.append("Participation stakes:")
        for record in penalty_records:
            if record.get("status") == "waived":
                lines.append(
                    f"- {record['display_name']} invoked grace; no influence forfeited."
                )
            elif record.get("deducted", 0) > 0 and record.get("faction"):
                lines.append(
                    f"- {record['display_name']} forfeits {record['deducted']} {record['faction']} influence."
                )
            else:
                lines.append(
                    f"- {record['display_name']} lacked influence to cover the {record['pledge_amount']} pledge."
                )
            remaining = record.get("remaining_debt", 0)
            if remaining:
                lines.append(f"  Outstanding debt recorded: {remaining} influence.")
    return lines


__all__ = ["compute_winner", "build_announcement_body", "build_resolution_body"]

