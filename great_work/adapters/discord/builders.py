"""Discord embed/message builders.

Pure-ish construction helpers for Discord UI objects. Keeping these in a
separate module makes them easy to unit test and reuse across handlers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import discord


def build_status_embed(data: Dict[str, Any]) -> discord.Embed:
    """Construct the status embed shown by `/status`.

    The input `data` is the dict returned by `GameService.player_status`.
    """

    embed = discord.Embed(
        title=f"Status — {data['display_name']}",
        colour=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Reputation",
        value=f"{data['reputation']} (cap {data['influence_cap']})",
        inline=False,
    )

    influence_lines = [
        f"{faction.capitalize()}: {value}"
        for faction, value in sorted(data["influence"].items())
    ]
    influence_text = "\n".join(influence_lines) if influence_lines else "None"
    embed.add_field(name="Influence", value=influence_text, inline=False)

    cooldowns = data.get("cooldowns") or {}
    if cooldowns:
        cooldown_lines = [f"{key}: {value} digests" for key, value in cooldowns.items()]
        embed.add_field(name="Cooldowns", value="\n".join(cooldown_lines), inline=False)

    thresholds = data.get("thresholds") or {}
    if thresholds:
        threshold_lines = [
            f"{action}: rep ≥ {value}" for action, value in sorted(thresholds.items())
        ]
        embed.add_field(
            name="Action Thresholds", value="\n".join(threshold_lines), inline=False
        )

    contracts = data.get("contracts", {})
    if contracts:
        contract_lines: List[str] = []
        for faction, payload in sorted(contracts.items()):
            contract_lines.append(
                f"{faction.capitalize()}: {payload.get('scholars', 0)} scholar(s), upkeep {payload.get('upkeep', 0)}, debt {payload.get('outstanding', 0)}"
            )
        embed.add_field(
            name="Contract Upkeep", value="\n".join(contract_lines), inline=False
        )

    sentiments = data.get("faction_sentiments") or {}
    if sentiments:
        sentiment_lines = []
        for faction, payload in sorted(sentiments.items()):
            avg = payload.get("average", 0.0)
            count = payload.get("count", 0)
            sentiment_lines.append(
                f"{faction.capitalize()}: Δ {avg:+.2f} ({count} scholar{'s' if count != 1 else ''})"
            )
        embed.add_field(
            name="Faction Sentiment", value="\n".join(sentiment_lines), inline=False
        )

    relationships = data.get("relationships") or []
    if relationships:
        relationship_lines: List[str] = []
        for entry in relationships[:5]:
            feeling = entry.get("feeling", 0.0)
            summary_parts: List[str] = []
            if entry.get("active_mentorship"):
                summary_parts.append("active mentorship")
            elif entry.get("last_mentorship_event"):
                summary_parts.append(entry["last_mentorship_event"])
            track = entry.get("track")
            tier = entry.get("tier")
            if track:
                summary_parts.append(f"track {track}{'/' + tier if tier else ''}")
            sidecast = entry.get("sidecast_arc")
            if sidecast:
                phase = entry.get("last_sidecast_phase") or "ongoing"
                summary_parts.append(f"sidecast {sidecast} ({phase})")
            summary = ", ".join(summary_parts) if summary_parts else "relationship"
            timeline: List[str] = []
            for item in entry.get("history", [])[:2]:
                stamp = item.get("timestamp")
                if stamp and isinstance(stamp, str):
                    stamp_display = stamp.split("T")[0]
                else:
                    stamp_display = "recent"
                if item.get("type") == "mentorship":
                    timeline.append(f"{stamp_display}: mentorship {item.get('event')}")
                else:
                    timeline.append(f"{stamp_display}: sidecast {item.get('phase')}")
            history_text = " | ".join(timeline)
            line = f"{entry['scholar']}: Δ {feeling:+.1f} ({summary})"
            if history_text:
                line += f"\n   {history_text}"
            relationship_lines.append(line)
        if len(relationships) > 5:
            relationship_lines.append(f"… plus {len(relationships) - 5} more")
        embed.add_field(
            name="Mentorship & Sidecasts", value="\n".join(relationship_lines), inline=False
        )

    commitments = data.get("commitments") or []
    if commitments:
        commitment_lines: List[str] = []
        for entry in commitments[:4]:
            relationship_pct = entry.get("relationship_modifier", 0.0) * 100
            end_at = entry.get("end_at")
            if isinstance(end_at, datetime):
                end_text = end_at.strftime("%Y-%m-%d")
            else:
                end_text = str(end_at) if end_at else "ongoing"
            commitment_lines.append(
                f"{(entry.get('faction') or 'Unaligned').capitalize()}: {entry.get('status', 'active')} (Δ {relationship_pct:+.1f}%, ends {end_text})"
            )
        embed.add_field(
            name="Seasonal Commitments", value="\n".join(commitment_lines), inline=False
        )

    investments = data.get("investments") or []
    if investments:
        invest_lines = [
            f"{entry.get('faction', 'unknown').capitalize()}: {entry.get('amount', 0)} influence"
            for entry in investments[:4]
        ]
        embed.add_field(name="Investments", value="\n".join(invest_lines), inline=False)

    endowments = data.get("archive_endowments") or []
    if endowments:
        endow_lines = [
            f"{entry.get('program', 'program')}: {entry.get('amount', 0)} influence"
            for entry in endowments[:4]
        ]
        embed.add_field(
            name="Archive Endowments", value="\n".join(endow_lines), inline=False
        )

    embed.set_footer(text="Status generated via /status")
    return embed


__all__ = ["build_status_embed"]


def build_theory_reference_embed(snapshot: Dict[str, Any]) -> discord.Embed:
    """Build an embed summarizing recent theories for players."""

    embed = discord.Embed(
        title="Theory Reference",
        colour=discord.Color.purple(),
        timestamp=datetime.now(timezone.utc),
    )
    summary = (
        f"Active {snapshot.get('active', 0)} • Expired {snapshot.get('expired', 0)} • "
        f"Unscheduled {snapshot.get('unscheduled', 0)}"
    )
    embed.description = summary + "\nPin this snapshot for quick theory lookups."

    from .handlers import _clamp_text  # local import to avoid cycles

    for entry in snapshot.get("theories", []):
        supporters = entry.get("supporters") or []
        if supporters:
            supporter_preview = ", ".join(supporters[:4])
            remaining_supporters = len(supporters) - 4
            if remaining_supporters > 0:
                supporter_preview += f" … +{remaining_supporters}"
        else:
            supporter_preview = "—"

        days_remaining = entry.get("days_remaining")
        status = entry.get("status", "unscheduled")
        if status == "active":
            if days_remaining is None:
                status_text = "Active"
            elif days_remaining > 1:
                status_text = f"Active • {days_remaining}d remaining"
            elif days_remaining == 1:
                status_text = "Active • 1d remaining"
            elif days_remaining == 0:
                status_text = "Active • resolves today"
            else:
                status_text = "Active"
        elif status == "expired":
            status_text = "Expired"
        else:
            status_text = "Unscheduled"

        theory_text = _clamp_text(entry.get("theory", ""))
        confidence_text = entry.get("confidence_display", entry.get("confidence", "")).strip()
        field_lines = [theory_text]
        if confidence_text:
            field_lines.append(f"Confidence: {confidence_text}")
        field_lines.append(f"Deadline: {entry.get('deadline_display', '—')} ({status_text})")
        field_lines.append(f"Supporters: {supporter_preview}")
        field_lines.append(f"Submitted: {entry.get('submitted_display', '—')}")

        field_value = _clamp_text("\n".join(field_lines))[:1024]
        embed.add_field(
            name=(
                f"[{entry.get('id')}] {entry.get('player_display')}"
                if entry.get("player_display")
                else f"Theory {entry.get('id')}"
            ),
            value=field_value,
            inline=False,
        )

    return embed


def build_recruit_odds_lines(
    odds: list[dict], *, base_chance: float, scholar_id: str
) -> list[str]:
    """Build message lines for the recruit_odds command."""

    lines: list[str] = [f"**Recruitment odds for {scholar_id}**"]
    lines.append(f"Base chance before modifiers: {base_chance * 100:.1f}%")
    relationship_modifier = odds[0]["relationship_modifier"] if odds else 0.0
    cooldown_info = odds[0]["cooldown_remaining"] if odds else 0
    if cooldown_info:
        lines.append(
            f"Recruitment cooldown active — penalties apply for the next {cooldown_info} digests."
        )
    if relationship_modifier:
        lines.append(
            "Scholar attitude modifier: {:+.1f}% (based on mentorship/sidecast history).".format(
                relationship_modifier * 100,
            )
        )
    lines.append("")
    for entry in odds:
        faction = entry["faction"].capitalize()
        chance_pct = entry["chance"] * 100
        base_pct = entry.get("base_chance", entry["chance"]) * 100
        rel_pct = entry.get("relationship_modifier", 0.0) * 100
        influence_bonus = entry["influence_bonus"] * 100
        influence_value = entry["influence"]
        cooldown_text = "halved" if entry["cooldown_active"] else "normal"
        lines.append(
            "• {faction}: {chance:.1f}% (base {base:.1f}%, relationship {rel:+.1f}%, influence {influence} ➜ +{bonus:.1f}%, cooldown {cooldown})".format(
                faction=faction,
                chance=chance_pct,
                base=base_pct,
                rel=rel_pct,
                influence=influence_value,
                bonus=influence_bonus,
                cooldown=cooldown_text,
            )
        )
    return lines

