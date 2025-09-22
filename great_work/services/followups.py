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

from ..models import PressRelease


def build_symposium_reprimand_press(
    *,
    display_name: str,
    faction: str,
    penalty_influence: int,
    penalty_reputation: int,
    reprisal_level: int,
    remaining: int,
    player_id: str,
) -> PressRelease:
    headline = f"Symposium Reprimand: {display_name}".rstrip()
    impacts = []
    if penalty_influence:
        impacts.append(f"{penalty_influence} influence seized by {faction}")
    if penalty_reputation:
        impacts.append(f"{penalty_reputation} reputation deducted")
    impact_text = "; ".join(impacts) if impacts else "Public reprimand issued"
    body = (
        f"{display_name} faces a symposium reprisal from {faction}. {impact_text}. "
        f"Outstanding debt: {remaining}. Reprisal level now {reprisal_level}."
    )
    return PressRelease(
        type="symposium_reprimand",
        headline=headline,
        body=body,
        metadata={
            "player_id": player_id,
            "faction": faction,
            "reprisal_level": reprisal_level,
            "remaining": remaining,
            "penalty_influence": penalty_influence,
            "penalty_reputation": penalty_reputation,
        },
    )

