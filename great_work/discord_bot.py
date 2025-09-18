"""Discord bot entry point for The Great Work."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .models import ConfidenceLevel, ExpeditionPreparation
from .service import GameService

logger = logging.getLogger(__name__)


def build_bot(db_path: Path, intents: Optional[discord.Intents] = None) -> commands.Bot:
    intents = intents or discord.Intents.default()
    bot = commands.Bot(command_prefix="/", intents=intents)
    service = GameService(db_path)

    @bot.event
    async def on_ready() -> None:
        logger.info("Great Work bot connected as %s", bot.user)
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d commands", len(synced))
        except Exception as exc:  # pragma: no cover - logging only
            logger.exception("Failed to sync commands: %s", exc)

    @app_commands.command(name="submit_theory", description="Submit a theory to the Gazette")
    @app_commands.describe(
        theory="The bold claim you are making",
        confidence="Confidence level",
        supporters="Comma separated scholar IDs",
        deadline="Counter-claim deadline (text)",
    )
    async def submit_theory(interaction: discord.Interaction, theory: str, confidence: str, supporters: str, deadline: str):
        try:
            level = ConfidenceLevel(confidence)
        except ValueError:
            await interaction.response.send_message(
                f"Invalid confidence {confidence}. Choose from {[c.value for c in ConfidenceLevel]}",
                ephemeral=True,
            )
            return
        supporter_list = [s.strip() for s in supporters.split(",") if s.strip()]
        press = service.submit_theory(
            player_id=str(interaction.user.display_name),
            theory=theory,
            confidence=level,
            supporters=supporter_list,
            deadline=deadline,
        )
        await interaction.response.send_message(f"{press.headline}\n{press.body}")

    @app_commands.command(name="launch_expedition", description="Queue an expedition for resolution")
    @app_commands.describe(
        code="Expedition code",
        objective="Objective statement",
        expedition_type="Expedition type (think_tank, field, great_project)",
        team="Comma separated scholar IDs",
        funding="Comma separated factions",
        prep_depth="shallow or deep",
        confidence="Confidence wager",
        think_tank="Think tank bonus",
        expertise="Expertise bonus",
        site_friction="Site friction penalty",
        political_friction="Political friction penalty",
    )
    async def launch_expedition(
        interaction: discord.Interaction,
        code: str,
        objective: str,
        expedition_type: str,
        team: str,
        funding: str,
        prep_depth: str,
        confidence: str,
        think_tank: int,
        expertise: int,
        site_friction: int,
        political_friction: int,
    ) -> None:
        try:
            level = ConfidenceLevel(confidence)
        except ValueError:
            await interaction.response.send_message("Invalid confidence level", ephemeral=True)
            return
        preparation = ExpeditionPreparation(
            think_tank_bonus=think_tank,
            expertise_bonus=expertise,
            site_friction=site_friction,
            political_friction=political_friction,
        )
        team_list = [s.strip() for s in team.split(",") if s.strip()]
        funding_list = [s.strip() for s in funding.split(",") if s.strip()]
        press = service.queue_expedition(
            code=code,
            player_id=str(interaction.user.display_name),
            expedition_type=expedition_type,
            objective=objective,
            team=team_list,
            funding=funding_list,
            preparation=preparation,
            prep_depth=prep_depth,
            confidence=level,
        )
        await interaction.response.send_message(f"{press.headline}\n{press.body}")

    @app_commands.command(name="resolve_expeditions", description="Resolve all pending expeditions")
    async def resolve_expeditions(interaction: discord.Interaction) -> None:
        digest_releases = service.advance_digest()
        releases = digest_releases + service.resolve_pending_expeditions()
        if not releases:
            await interaction.response.send_message("No expeditions waiting.")
            return
        text = "\n\n".join(f"{press.headline}\n{press.body}" for press in releases)
        await interaction.response.send_message(text)

    @app_commands.command(name="recruit", description="Attempt to recruit a scholar")
    @app_commands.describe(
        scholar_id="Scholar identifier",
        faction="Faction making the offer",
    )
    async def recruit(
        interaction: discord.Interaction,
        scholar_id: str,
        faction: str,
    ) -> None:
        try:
            success, press = service.attempt_recruitment(
                player_id=str(interaction.user.display_name),
                scholar_id=scholar_id,
                faction=faction,
            )
        except PermissionError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        prefix = "Success" if success else "Failure"
        await interaction.response.send_message(f"{prefix}: {press.headline}\n{press.body}")

    @app_commands.command(name="status", description="Show your current influence and cooldowns")
    async def status(interaction: discord.Interaction) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        data = service.player_status(str(interaction.user.display_name))
        lines = [f"Reputation: {data['reputation']} (cap {data['influence_cap']})"]
        lines.append("Influence:")
        for faction, value in sorted(data["influence"].items()):
            lines.append(f" - {faction}: {value}")
        if data["cooldowns"]:
            lines.append("Cooldowns:")
            for key, value in data["cooldowns"].items():
                lines.append(f" - {key}: {value} digests")
        else:
            lines.append("No active cooldowns.")
        if data["thresholds"]:
            lines.append("Action thresholds:")
            for action, value in sorted(data["thresholds"].items()):
                lines.append(f" - {action}: requires reputation {value}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="wager", description="Show the confidence wager table and thresholds")
    async def wager(interaction: discord.Interaction) -> None:
        reference = service.wager_reference()
        lines = ["Confidence wagers:"]
        for level, payload in reference["wagers"].items():
            suffix = " (triggers recruitment cooldown)" if payload["triggers_recruitment_cooldown"] else ""
            lines.append(
                f" - {level}: reward {payload['reward']}, penalty {payload['penalty']}{suffix}"
            )
        lines.append("")
        lines.append("Action thresholds:")
        for action, value in sorted(reference["action_thresholds"].items()):
            lines.append(f" - {action}: {value}")
        bounds = reference["reputation_bounds"]
        lines.append("")
        lines.append(f"Reputation bounds: {bounds['min']} to {bounds['max']}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="gazette", description="Show recent Gazette headlines")
    async def gazette(interaction: discord.Interaction, limit: int = 5) -> None:
        if limit <= 0 or limit > 20:
            await interaction.response.send_message("Limit must be between 1 and 20", ephemeral=True)
            return
        records = service.export_press_archive(limit=limit)
        if not records:
            await interaction.response.send_message("No Gazette entries recorded yet.", ephemeral=True)
            return
        lines = ["Recent Gazette entries:"]
        for record in records:
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f" - {timestamp} | {record.release.headline}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="export_log", description="Export recent events and press")
    async def export_log(interaction: discord.Interaction, limit: int = 10) -> None:
        if limit <= 0 or limit > 50:
            await interaction.response.send_message("Limit must be between 1 and 50", ephemeral=True)
            return
        log = service.export_log(limit=limit)
        press_lines = [f"Press ({len(log['press'])} entries):"]
        for record in log["press"]:
            press_lines.append(f" - {record.timestamp.isoformat()} | {record.release.headline}")
        event_lines = [f"Events ({len(log['events'])} entries):"]
        for event in log["events"]:
            event_lines.append(f" - {event.timestamp.isoformat()} {event.action}")
        await interaction.response.send_message("\n".join(press_lines + [""] + event_lines), ephemeral=True)

    bot.tree.add_command(submit_theory)
    bot.tree.add_command(launch_expedition)
    bot.tree.add_command(resolve_expeditions)
    bot.tree.add_command(recruit)
    bot.tree.add_command(status)
    bot.tree.add_command(wager)
    bot.tree.add_command(gazette)
    bot.tree.add_command(export_log)
    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable must be set")
    db_path = Path(os.environ.get("GREAT_WORK_DB", "great_work.db"))
    bot = build_bot(db_path)
    bot.run(token)


__all__ = ["build_bot", "main"]
