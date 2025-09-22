"""Follow-up and reminder helpers."""

from __future__ import annotations


def build_symposium_reminder_body(
    *,
    player_display: str,
    topic: str,
    reminder_level: str,
    pledged_amount: int,
    grace_remaining: int,
) -> str:
    """Compose the reminder body text for symposium voting.

    reminder_level: "first" or "escalation".
    """

    if reminder_level == "escalation":
        return (
            f"{player_display}, the Academy notes you have not yet cast a vote on "
            f"'{topic}'. Missing this symposium will forfeit {pledged_amount} influence. "
            "Use /symposium_vote before resolution to keep your pledge intact."
        )

    if grace_remaining > 0:
        plural = "s" if grace_remaining != 1 else ""
        grace_text = f"You have {grace_remaining} grace miss{plural} remaining; voting preserves it."
    else:
        grace_text = f"You are out of grace—silence will cost {pledged_amount} influence."
    return (
        f"{player_display} is requested to cast a vote on '{topic}'. "
        f"{grace_text} Use /symposium_vote to weigh in."
    )


__all__ = ["build_symposium_reminder_body"]

