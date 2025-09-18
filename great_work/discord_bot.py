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
            logger.exception("Failed to sync commands: %%s", exc)

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
        releases = service.resolve_pending_expeditions()
        if not releases:
            await interaction.response.send_message("No expeditions waiting.")
            return
        text = "\n\n".join(f"{press.headline}\n{press.body}" for press in releases)
        await interaction.response.send_message(text)

    bot.tree.add_command(submit_theory)
    bot.tree.add_command(launch_expedition)
    bot.tree.add_command(resolve_expeditions)
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
