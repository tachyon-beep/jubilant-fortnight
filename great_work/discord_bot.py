"""Discord bot entry point for The Great Work."""
from __future__ import annotations

import io
import json
import atexit
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .analytics import collect_calibration_snapshot, write_calibration_snapshot
from .models import ConfidenceLevel, ExpeditionPreparation, PressRelease, PressRecord
from .scheduler import GazetteScheduler
from .service import GameService
from .telemetry import get_telemetry
from .telemetry_decorator import track_command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelRouter:
    """Configures which Discord channels receive automated posts."""

    orders: Optional[int]
    gazette: Optional[int]
    table_talk: Optional[int]
    admin: Optional[int]
    upcoming: Optional[int]

    @staticmethod
    def from_env() -> "ChannelRouter":
        def _parse(env_key: str) -> Optional[int]:
            value = os.environ.get(env_key)
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                logger.warning("Invalid channel id %s for %s", value, env_key)
                return None

        return ChannelRouter(
            orders=_parse("GREAT_WORK_CHANNEL_ORDERS"),
            gazette=_parse("GREAT_WORK_CHANNEL_GAZETTE"),
            table_talk=_parse("GREAT_WORK_CHANNEL_TABLE_TALK"),
            admin=_parse("GREAT_WORK_CHANNEL_ADMIN"),
            upcoming=_parse("GREAT_WORK_CHANNEL_UPCOMING"),
        )


async def _post_to_channel(
    bot: commands.Bot,
    channel_id: Optional[int],
    content: str,
    *,
    purpose: str,
) -> None:
    """Send content to a configured channel if possible."""

    if channel_id is None:
        logger.debug("Skipping %s post; channel not configured", purpose)
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Failed to locate %s channel with id %s", purpose, channel_id)
        return
    try:
        await channel.send(content)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to send %s message", purpose)


async def _post_file_to_channel(
    bot: commands.Bot,
    channel_id: Optional[int],
    file_path: Path,
    *,
    caption: str,
    purpose: str,
) -> None:
    """Send a file attachment to a configured channel."""

    if channel_id is None:
        logger.debug("Skipping %s file post; channel not configured", purpose)
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Failed to locate %s channel with id %s", purpose, channel_id)
        return
    try:
        await channel.send(content=caption, file=discord.File(str(file_path)))
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to send %s file message", purpose)


_MAX_MESSAGE_LENGTH = 1900


def _clamp_text(text: str) -> str:
    """Ensure Discord-compatible message length."""

    if len(text) <= _MAX_MESSAGE_LENGTH:
        return text
    return text[: _MAX_MESSAGE_LENGTH - 1].rstrip() + "…"


def _format_message(lines: Iterable[str]) -> str:
    """Join message lines and clamp to Discord limits."""

    message = "\n".join(line for line in lines if line is not None)
    return _clamp_text(message)


def _format_press(press: PressRelease) -> str:
    return f"**{press.headline}**\n{press.body}"


def build_bot(db_path: Path, intents: Optional[discord.Intents] = None) -> commands.Bot:
    intents = intents or discord.Intents.default()
    app_id_raw = os.environ.get("DISCORD_APP_ID")
    application_id: Optional[int] = None
    if app_id_raw:
        try:
            application_id = int(app_id_raw)
        except ValueError:
            logger.warning("Invalid DISCORD_APP_ID: %s", app_id_raw)
    bot = commands.Bot(command_prefix="/", intents=intents, application_id=application_id)
    service = GameService(db_path)
    setattr(bot, "state_service", service)
    router = ChannelRouter.from_env()
    scheduler: Optional[GazetteScheduler] = None

    def _info_channel() -> Optional[int]:
        """Prefer table-talk for informational posts, fall back to gazette/orders."""

        return (
            router.table_talk
            or router.gazette
            or router.upcoming
            or router.orders
        )

    async def _respond_and_broadcast(
        interaction: discord.Interaction,
        lines: Iterable[str],
        *,
        purpose: str,
        header: Optional[str] = None,
        channel: Optional[int] = None,
        ephemeral: bool = True,
    ) -> None:
        """Send an ephemeral response and mirror it to a public channel."""

        message = _format_message(lines)
        await interaction.response.send_message(message, ephemeral=ephemeral)
        target_channel = channel if channel is not None else _info_channel()
        if target_channel is None:
            return
        public_message = message if not header else _clamp_text(f"{header}\n{message}")
        if not public_message.strip():
            return
        await _post_to_channel(bot, target_channel, public_message, purpose=purpose)

    def _shutdown_scheduler() -> None:  # pragma: no cover - process shutdown hook
        if scheduler is not None:
            scheduler.shutdown()

    atexit.register(_shutdown_scheduler)

    async def _flush_admin_notifications() -> None:
        notes = service.drain_admin_notifications()
        if not notes:
            return
        if router.admin is None:
            for note in notes:
                logger.info("ADMIN: %s", note)
            return
        for note in notes:
            await _post_to_channel(bot, router.admin, note, purpose="admin")

    @bot.event
    async def on_ready() -> None:
        nonlocal scheduler
        logger.info("Great Work bot connected as %s", bot.user)
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d commands", len(synced))
        except Exception as exc:  # pragma: no cover - logging only
            logger.exception("Failed to sync commands: %s", exc)
        if scheduler is None and any(x is not None for x in (router.gazette, router.admin, router.upcoming)):
            publisher = None
            if router.gazette is not None:
                publisher = lambda press: asyncio.run_coroutine_threadsafe(
                    _post_to_channel(
                        bot,
                        router.gazette,
                        _format_press(press),
                        purpose="gazette",
                    ),
                    bot.loop,
                )

            admin_publisher = None
            admin_file_publisher = None
            upcoming_publisher = None
            if router.admin is not None:
                admin_publisher = lambda message: asyncio.run_coroutine_threadsafe(
                    _post_to_channel(
                        bot,
                        router.admin,
                        message,
                        purpose="admin",
                    ),
                    bot.loop,
                )
                admin_file_publisher = lambda path, caption: asyncio.run_coroutine_threadsafe(
                    _post_file_to_channel(
                        bot,
                        router.admin,
                        path,
                        caption=caption,
                        purpose="admin",
                    ),
                    bot.loop,
                )
            if router.upcoming is not None:
                upcoming_publisher = lambda message: asyncio.run_coroutine_threadsafe(
                    _post_to_channel(
                        bot,
                        router.upcoming,
                        message,
                        purpose="upcoming",
                    ),
                    bot.loop,
                )

            scheduler = GazetteScheduler(
                service,
                publisher=publisher,
                admin_publisher=admin_publisher,
                admin_file_publisher=admin_file_publisher,
                upcoming_publisher=upcoming_publisher,
            )
            scheduler.start()
            logger.info("Started Gazette scheduler publishing to %s", router.gazette)

    @app_commands.command(name="submit_theory", description="Submit a theory to the Gazette")
    @track_command
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
            await _flush_admin_notifications()
            return
        supporter_list = [s.strip() for s in supporters.split(",") if s.strip()]
        try:
            press = service.submit_theory(
                player_id=str(interaction.user.display_name),
                theory=theory,
                confidence=level,
                supporters=supporter_list,
                deadline=deadline,
            )
        except GameService.ModerationRejectedError as exc:
            await interaction.response.send_message(
                f"Moderation blocked that submission: {exc}",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return
        message = _format_press(press)
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")
        await _flush_admin_notifications()

    @app_commands.command(name="launch_expedition", description="Queue an expedition for resolution")
    @track_command
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
            await _flush_admin_notifications()
            return
        preparation = ExpeditionPreparation(
            think_tank_bonus=think_tank,
            expertise_bonus=expertise,
            site_friction=site_friction,
            political_friction=political_friction,
        )
        team_list = [s.strip() for s in team.split(",") if s.strip()]
        funding_list = [s.strip() for s in funding.split(",") if s.strip()]
        try:
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
        except GameService.ModerationRejectedError as exc:
            await interaction.response.send_message(
                f"Moderation blocked that expedition objective: {exc}",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return
        message = _format_press(press)
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")
        await _flush_admin_notifications()

    @app_commands.command(name="resolve_expeditions", description="Resolve all pending expeditions")
    @track_command
    async def resolve_expeditions(interaction: discord.Interaction) -> None:
        try:
            digest_releases = service.advance_digest()
            releases = digest_releases + service.resolve_pending_expeditions()
        except GameService.GamePausedError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        if not releases:
            await interaction.response.send_message("No expeditions waiting.")
            await _flush_admin_notifications()
            return
        text = "\n\n".join(_format_press(press) for press in releases)
        await interaction.response.send_message(text)
        await _post_to_channel(bot, router.orders, text, purpose="orders")
        await _flush_admin_notifications()

    @app_commands.command(name="recruit_odds", description="Preview recruitment odds for each faction")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar identifier",
        base_chance="Base success chance before modifiers (default 0.6)",
    )
    async def recruit_odds(
        interaction: discord.Interaction,
        scholar_id: str,
        base_chance: app_commands.Range[float, 0.0, 1.0] = 0.6,
    ) -> None:
        player_id = str(interaction.user.display_name)
        service.ensure_player(player_id, interaction.user.display_name)
        try:
            odds = service.recruitment_odds(
                player_id=player_id,
                scholar_id=scholar_id,
                base_chance=base_chance,
            )
        except PermissionError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        lines = [f"**Recruitment odds for {scholar_id}**"]
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
            relationship_pct = entry.get("relationship_modifier", 0.0) * 100
            influence_bonus = entry["influence_bonus"] * 100
            influence_value = entry["influence"]
            cooldown_text = "halved" if entry["cooldown_active"] else "normal"
            lines.append(
                "• {faction}: {chance:.1f}% (base {base:.1f}%, relationship {rel:+.1f}%, influence {influence} ➜ +{bonus:.1f}%, cooldown {cooldown})".format(
                    faction=faction,
                    chance=chance_pct,
                    base=base_pct,
                    rel=relationship_pct,
                    influence=influence_value,
                    bonus=influence_bonus,
                    cooldown=cooldown_text,
                )
            )

        header = f"**/symposium_backlog requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="symposium-backlog",
            header=header,
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="recruit", description="Attempt to recruit a scholar")
    @track_command
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
            await _flush_admin_notifications()
            return
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        prefix = "Success" if success else "Failure"
        message = f"{prefix}: {press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")
        await _flush_admin_notifications()

    @app_commands.command(name="mentor", description="Begin mentoring a scholar")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar identifier",
        career_track="Optional career track (Academia or Industry)",
    )
    async def mentor(
        interaction: discord.Interaction,
        scholar_id: str,
        career_track: str | None = None,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            press = service.queue_mentorship(
                player_id=str(interaction.user.display_name),
                scholar_id=scholar_id,
                career_track=career_track,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @app_commands.command(name="assign_lab", description="Assign a mentored scholar to a new career track")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar identifier",
        career_track="Career track (Academia or Industry)",
    )
    async def assign_lab(
        interaction: discord.Interaction,
        scholar_id: str,
        career_track: str,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            press = service.assign_lab(
                player_id=str(interaction.user.display_name),
                scholar_id=scholar_id,
                career_track=career_track,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @app_commands.command(name="set_nickname", description="Assign a nickname to a scholar")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar identifier (e.g., SCH-001)",
        nickname="Nickname to record",
    )
    async def set_nickname(
        interaction: discord.Interaction,
        scholar_id: str,
        nickname: str,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            response = service.set_scholar_nickname(
                player_id=str(interaction.user.display_name),
                display_name=interaction.user.display_name,
                scholar_id=scholar_id,
                nickname=nickname,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        existing = service.state.list_scholar_nicknames(scholar_id)[:5]
        if existing:
            existing_lines = [
                f"• {entry['nickname']} — {entry['player_id']} ({entry['created_at']})"
                for entry in existing
            ]
            response += "\n\nRecent nicknames:\n" + "\n".join(existing_lines)

        await interaction.response.send_message(response)
        await _flush_admin_notifications()

    @app_commands.command(name="share_press", description="Share a press release to table talk")
    @track_command
    @app_commands.describe(
        press_id="Press release identifier (use /archive_link to look up IDs)",
    )
    async def share_press(
        interaction: discord.Interaction,
        press_id: int,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            message = service.share_press_release(
                player_id=str(interaction.user.display_name),
                display_name=interaction.user.display_name,
                press_id=press_id,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        target_channel_id = router.table_talk or router.gazette or router.orders
        if target_channel_id:
            await _post_to_channel(bot, target_channel_id, message, purpose="press_share")
        elif interaction.channel:
            try:
                await interaction.channel.send(message)
            except Exception:  # pragma: no cover - channel send failures logged
                logger.exception("Failed to send press share to current channel")

        await interaction.response.send_message(
            f"Shared press #{press_id} to the configured table-talk channel.",
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="poach", description="Attempt to poach another player's scholar")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar to poach",
        target_faction="Faction to recruit them to",
        academic_influence="Academic influence to offer (0-100)",
        government_influence="Government influence to offer (0-100)",
        industry_influence="Industry influence to offer (0-100)",
        religious_influence="Religious influence to offer (0-100)",
        foreign_influence="Foreign influence to offer (0-100)",
        guaranteed_funding="Offer guaranteed funding (true/false)",
        exclusive_research="Offer exclusive research rights (true/false)",
        leadership_role="Offer leadership position (true/false)",
    )
    async def poach(
        interaction: discord.Interaction,
        scholar_id: str,
        target_faction: str,
        academic_influence: int = 0,
        government_influence: int = 0,
        industry_influence: int = 0,
        religious_influence: int = 0,
        foreign_influence: int = 0,
        guaranteed_funding: bool = False,
        exclusive_research: bool = False,
        leadership_role: bool = False,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)

        # Build influence offer
        influence_offer = {}
        if academic_influence > 0:
            influence_offer["academic"] = academic_influence
        if government_influence > 0:
            influence_offer["government"] = government_influence
        if industry_influence > 0:
            influence_offer["industry"] = industry_influence
        if religious_influence > 0:
            influence_offer["religious"] = religious_influence
        if foreign_influence > 0:
            influence_offer["foreign"] = foreign_influence

        if not influence_offer:
            await interaction.response.send_message("You must offer at least some influence!", ephemeral=True)
            await _flush_admin_notifications()
            return

        # Build terms
        terms = {}
        if guaranteed_funding:
            terms["guaranteed_funding"] = True
        if exclusive_research:
            terms["exclusive_research"] = True
        if leadership_role:
            terms["leadership_role"] = True

        try:
            offer_id, press_list = service.create_defection_offer(
                rival_id=str(interaction.user.display_name),
                scholar_id=scholar_id,
                target_faction=target_faction,
                influence_offer=influence_offer,
                terms=terms,
            )

            message = f"Offer #{offer_id} created!\n"
            for press in press_list:
                message += f"{press.headline}\n{press.body}\n"

            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
            await _flush_admin_notifications()
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()

    @app_commands.command(name="counter", description="Counter a rival's poaching attempt")
    @track_command
    @app_commands.describe(
        offer_id="ID of the offer to counter",
        academic_influence="Academic influence to offer (0-100)",
        government_influence="Government influence to offer (0-100)",
        industry_influence="Industry influence to offer (0-100)",
        religious_influence="Religious influence to offer (0-100)",
        foreign_influence="Foreign influence to offer (0-100)",
        guaranteed_funding="Offer guaranteed funding (true/false)",
        exclusive_research="Offer exclusive research rights (true/false)",
        leadership_role="Offer leadership position (true/false)",
    )
    async def counter(
        interaction: discord.Interaction,
        offer_id: int,
        academic_influence: int = 0,
        government_influence: int = 0,
        industry_influence: int = 0,
        religious_influence: int = 0,
        foreign_influence: int = 0,
        guaranteed_funding: bool = False,
        exclusive_research: bool = False,
        leadership_role: bool = False,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)

        # Build counter influence offer
        counter_influence = {}
        if academic_influence > 0:
            counter_influence["academic"] = academic_influence
        if government_influence > 0:
            counter_influence["government"] = government_influence
        if industry_influence > 0:
            counter_influence["industry"] = industry_influence
        if religious_influence > 0:
            counter_influence["religious"] = religious_influence
        if foreign_influence > 0:
            counter_influence["foreign"] = foreign_influence

        if not counter_influence:
            await interaction.response.send_message("You must offer at least some influence!", ephemeral=True)
            await _flush_admin_notifications()
            return

        # Build terms
        counter_terms = {}
        if guaranteed_funding:
            counter_terms["guaranteed_funding"] = True
        if exclusive_research:
            counter_terms["exclusive_research"] = True
        if leadership_role:
            counter_terms["leadership_role"] = True

        try:
            counter_id, press_list = service.counter_offer(
                player_id=str(interaction.user.display_name),
                original_offer_id=offer_id,
                counter_influence=counter_influence,
                counter_terms=counter_terms,
            )

            message = f"Counter-offer #{counter_id} created!\n"
            for press in press_list:
                message += f"{press.headline}\n{press.body}\n"

            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
            await _flush_admin_notifications()
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()

    @app_commands.command(name="view_offers", description="View active offers involving your scholars")
    @track_command
    async def view_offers(interaction: discord.Interaction) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)

        try:
            offers = service.list_player_offers(str(interaction.user.display_name))

            if not offers:
                await interaction.response.send_message("No active offers involving you.", ephemeral=True)
                await _flush_admin_notifications()
                return

            message = "**Active Offers:**\n"
            for offer in offers:
                scholar = service.state.get_scholar(offer.scholar_id)
                message += f"\n**Offer #{offer.id}** - {offer.status.upper()}\n"
                message += f"Scholar: {scholar.name if scholar else offer.scholar_id}\n"
                message += f"Type: {offer.offer_type}\n"
                message += f"Rival: {offer.rival_id}, Patron: {offer.patron_id}\n"
                message += f"Influence: {', '.join(f'{v} {k}' for k, v in offer.influence_offered.items())}\n"
                if offer.terms:
                    message += f"Terms: {offer.terms}\n"
                message += f"Created: {offer.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                snapshot = offer.relationship_snapshot or {}
                rival_snap = snapshot.get("rival", {})
                patron_snap = snapshot.get("patron", {})
                if rival_snap or patron_snap:
                    rival_name = rival_snap.get("display_name") or offer.rival_id
                    patron_name = patron_snap.get("display_name") or offer.patron_id
                    rival_feeling = rival_snap.get("feeling")
                    patron_feeling = patron_snap.get("feeling")
                    if rival_feeling is not None and patron_feeling is not None:
                        message += (
                            "Loyalty snapshot: "
                            f"rival {rival_name} {rival_feeling:+.1f}, "
                            f"patron {patron_name} {patron_feeling:+.1f}\n"
                        )
                
            await interaction.response.send_message(message, ephemeral=True)
            await _flush_admin_notifications()
        except Exception as exc:
            await interaction.response.send_message(f"Error: {exc}", ephemeral=True)
            await _flush_admin_notifications()

    @app_commands.command(name="conference", description="Launch a conference to debate a theory")
    @track_command
    @app_commands.describe(
        theory_id="Theory ID to debate",
        confidence="Confidence wager level",
        supporters="Comma-separated scholar IDs supporting the theory",
        opposition="Comma-separated scholar IDs opposing the theory",
    )
    async def conference(
        interaction: discord.Interaction,
        theory_id: int,
        confidence: str,
        supporters: str,
        opposition: str,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            confidence_level = ConfidenceLevel(confidence)
        except ValueError:
            await interaction.response.send_message(
                f"Invalid confidence {confidence}. Choose from {[c.value for c in ConfidenceLevel]}",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return

        supporter_list = [s.strip() for s in supporters.split(",") if s.strip()]
        opposition_list = [s.strip() for s in opposition.split(",") if s.strip()]

        try:
            press = service.launch_conference(
                player_id=str(interaction.user.display_name),
                theory_id=theory_id,
                confidence=confidence_level,
                supporters=supporter_list,
                opposition=opposition_list,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
            await _flush_admin_notifications()
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()

    @app_commands.command(name="symposium_vote", description="Cast your vote on the current symposium topic")
    @track_command
    @app_commands.describe(
        vote="Your vote: 1 (support), 2 (oppose), 3 (further study)",
    )
    async def symposium_vote(
        interaction: discord.Interaction,
        vote: int,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            press = service.vote_symposium(
                player_id=str(interaction.user.display_name),
                vote_option=vote,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.orders, message, purpose="orders")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @app_commands.command(name="symposium_propose", description="Propose a symposium topic for consideration")
    @track_command
    @app_commands.describe(
        topic="Title of the proposed symposium debate",
        description="Brief description that frames the question the academy should tackle",
    )
    async def symposium_propose(
        interaction: discord.Interaction,
        topic: str,
        description: str,
    ) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        try:
            press = service.submit_symposium_proposal(
                player_id=str(interaction.user.display_name),
                topic=topic,
                description=description,
            )
        except GameService.ModerationRejectedError as exc:
            await interaction.response.send_message(
                f"Moderation blocked that proposal: {exc}",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")
        await _flush_admin_notifications()

    @app_commands.command(name="symposium_proposals", description="List pending symposium proposals")
    @track_command
    async def symposium_proposals(interaction: discord.Interaction) -> None:
        now = datetime.now(timezone.utc)
        proposals = service.list_symposium_proposals(limit=5)
        if not proposals:
            await interaction.response.send_message(
                "No symposium proposals are pending. Submit one with /symposium_propose!",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return

        total = service.state.count_pending_symposium_proposals(now=now)
        backlog_cap = service.settings.symposium_max_backlog
        per_player_cap = service.settings.symposium_max_per_player
        expiry_days = service.settings.symposium_proposal_expiry_days

        slots_remaining = max(0, backlog_cap - total)
        lines = [
            f"**Pending Symposium Proposals ({total}/{backlog_cap}, {slots_remaining} slot(s) free)**",
            f"Each player may hold up to {per_player_cap} active proposal(s); entries expire after {expiry_days} days.",
            "",
        ]
        for proposal in proposals:
            created_at = proposal.get("created_at")
            created_str = (
                created_at.strftime("%Y-%m-%d %H:%M UTC") if created_at else "recently"
            )
            expires_at = proposal.get("expires_at")
            if expires_at:
                remaining = expires_at - now
                if remaining.total_seconds() <= 0:
                    expiry_str = "expired"
                elif remaining.days >= 1:
                    expiry_str = f"in {remaining.days}d"
                else:
                    hours = max(1, remaining.seconds // 3600)
                    expiry_str = f"in {hours}h"
                expires_display = f"expires {expires_at.strftime('%Y-%m-%d')} ({expiry_str})"
            else:
                expires_display = "no expiry"
            lines.append(
                f"• [{proposal['id']}] {proposal['topic']} — proposed by {proposal['proposer']} ({created_str}; {expires_display})"
            )
        header = f"**/symposium_proposals requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="symposium-proposals",
            header=header,
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="symposium_backlog", description="Show scoring details for pending symposium proposals")
    @track_command
    async def symposium_backlog(interaction: discord.Interaction) -> None:
        report = service.symposium_backlog_report()
        cfg = report.get("config", {})
        lines = [
            (
                f"**Symposium Backlog** "
                f"({report['backlog_size']}/{cfg.get('max_backlog')} slots; {report['slots_remaining']} free)"
            ),
            (
                "Scoring: "
                f"age weight {cfg.get('age_weight')}, max age {cfg.get('max_age_days')}d, "
                f"fresh bonus +{cfg.get('fresh_bonus')}, repeat penalty −{cfg.get('repeat_penalty')}"
            ),
        ]
        scoring = report.get("scoring") or []
        if scoring:
            lines.append("")
            lines.append("**Current Ranking**")
            for entry in scoring:
                components: list[str] = []
                age_contrib = entry.get("age_contribution")
                if age_contrib is not None:
                    components.append(f"{age_contrib:+.2f} age")
                fresh_bonus = entry.get("fresh_bonus")
                if fresh_bonus:
                    components.append(f"{fresh_bonus:+.2f} fresh")
                repeat_penalty = entry.get("repeat_penalty")
                if repeat_penalty:
                    components.append(f"-{repeat_penalty:.2f} repeat")
                if not components:
                    components.append("0.00 neutral")
                component_text = ", ".join(components)
                recent_flag = " (recent proposer)" if entry.get("recent_proposer") else ""
                lines.append(
                    "• {topic} — {name}: score {score:.2f} "
                    "[{components}; age {age:.1f}d]{flag}".format(
                        topic=entry.get("topic"),
                        name=entry.get("display_name"),
                        score=entry.get("score", 0.0),
                        components=component_text,
                        age=entry.get("age_days", 0.0),
                        flag=recent_flag,
                    )
                )
        else:
            lines.append("")
            lines.append("No proposals scored yet.")

        debt_rows = report.get("debts") or []
        if debt_rows:
            totals = report.get("debt_totals", {})
            lines.append("")
            lines.append(
                "**Outstanding Debts** (total {total} across {count} player(s))".format(
                    total=totals.get("total_outstanding", 0),
                    count=totals.get("players_in_debt", len(debt_rows)),
                )
            )
            sorted_rows = sorted(
                debt_rows,
                key=lambda row: (row.get("amount", 0), row.get("display_name", "")),
                reverse=True,
            )
            for row in sorted_rows:
                next_reprisal = row.get("next_reprisal_at") or "pending"
                lines.append(
                    "• {name} owes {amount} ({faction}) — reprisal lvl {level}, next reprisal {next_reprisal}".format(
                        name=row.get("display_name"),
                        amount=row.get("amount", 0),
                        faction=(row.get("faction") or "Unaligned").capitalize(),
                        level=row.get("reprisal_level", 0),
                        next_reprisal=next_reprisal,
                    )
                )
                if row.get("last_reprisal_at"):
                    lines.append(
                        "   Last reprisal {last} (cooldown {cooldown}d)".format(
                            last=row.get("last_reprisal_at"),
                            cooldown=row.get("cooldown_days", "?"),
                        )
                    )

        header = f"**/symposium_status requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="symposium-status",
            header=header,
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="symposium_status", description="Show your symposium pledge status and history")
    @track_command
    async def symposium_status(interaction: discord.Interaction) -> None:
        player_id = str(interaction.user.display_name)
        service.ensure_player(player_id, interaction.user.display_name)
        status = service.symposium_pledge_status(player_id)

        lines = [f"**Symposium Pledge Status — {status['display_name']}**"]
        lines.append(
            f"Current miss streak: {status['miss_streak']} | Grace remaining: {status['grace_remaining']} of {status['grace_limit']}"
        )
        if status.get("grace_window_start"):
            lines.append(f"Grace window reset: {status['grace_window_start']}")
        if status.get("last_voted_at"):
            lines.append(f"Last voted at: {status['last_voted_at']}")
        outstanding = status.get("outstanding_debt", 0)
        if outstanding:
            lines.append(f"Outstanding symposium debt: {outstanding} influence")

        current = status.get("current")
        if current:
            current_lines = ["", "**Active Symposium**"]
            current_lines.append(f"Topic: {current['topic']}")
            current_lines.append(f"Pledge: {current['pledge_amount']} influence")
            faction = current.get("faction")
            if faction:
                current_lines.append(f"Faction at stake: {faction}")
            current_lines.append(f"Status: {current.get('status', 'pending')}")
            lines.extend(current_lines)

        debts = status.get("debts") or []
        if debts:
            lines.append("")
            lines.append("**Outstanding Debts**")
            for debt in debts:
                faction = (debt.get("faction") or "Unaligned").capitalize()
                next_reprisal = debt.get("next_reprisal_at") or "pending"
                line = (
                    f"• {debt.get('amount', 0)} influence ({faction}) — "
                    f"reprisal lvl {debt.get('reprisal_level', 0)}, next reprisal {next_reprisal}"
                )
                lines.append(line)
                extra_bits: list[str] = []
                if debt.get("last_reprisal_at"):
                    extra_bits.append(f"last reprisal {debt['last_reprisal_at']}")
                if debt.get("updated_at"):
                    extra_bits.append(f"updated {debt['updated_at']}")
                if debt.get("cooldown_days") is not None:
                    extra_bits.append(f"cooldown {debt['cooldown_days']}d")
                if extra_bits:
                    lines.append("   " + "; ".join(extra_bits))

        history = status.get("history") or []
        if history:
            lines.append("")
            lines.append("**Recent Symposium Outcomes**")
            for entry in history:
                lines.append(
                    "• {topic} — {status} ({amount} influence{faction})".format(
                        topic=entry.get("topic") or f"Topic {entry['topic_id']}",
                        status=entry.get("status", "unknown"),
                        amount=entry.get("pledge_amount", 0),
                        faction=f" / {entry['faction']}" if entry.get("faction") else "",
                    )
                )
                if entry.get("status") == "debt" and entry.get("resolved_at") is None:
                    lines.append("  Debt outstanding until paid")
        else:
            lines.append("")
            lines.append("No prior symposium pledges on record.")

        header = f"**/symposium_status requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="symposium-status",
            header=header,
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="status", description="Show your current influence and cooldowns")
    @track_command
    async def status(interaction: discord.Interaction) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)
        data = service.player_status(str(interaction.user.display_name))
        lines = [f"**Status Snapshot — {data['display_name']}**"]
        lines.append(f"Reputation: {data['reputation']} (cap {data['influence_cap']})")
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
        contracts = data.get("contracts", {})
        if contracts:
            lines.append("")
            lines.append("Contract upkeep:")
            for faction, payload in sorted(contracts.items()):
                lines.append(
                    " - {faction}: {count} scholar(s), upkeep {upkeep}, debt {debt}".format(
                        faction=faction.capitalize(),
                        count=payload.get("scholars", 0),
                        upkeep=payload.get("upkeep", 0),
                        debt=payload.get("outstanding", 0),
                    )
                )
        relationships = data.get("relationships") or []
        if relationships:
            lines.append("")
            lines.append("Mentorship & Sidecast Links:")
            for entry in relationships:
                feeling = entry.get("feeling", 0.0)
                feeling_text = f"{feeling:+.1f}"
                detail_parts: List[str] = []
                if entry.get("active_mentorship"):
                    detail_parts.append("active mentorship")
                elif entry.get("last_mentorship_event"):
                    detail = entry.get("last_mentorship_event")
                    when = entry.get("last_mentorship_at") or "recently"
                    detail_parts.append(f"{detail} ({when})")
                track = entry.get("track")
                tier = entry.get("tier")
                if track:
                    detail_parts.append(f"track {track}{'/' + tier if tier else ''}")
                sidecast = entry.get("sidecast_arc")
                if sidecast:
                    phase = entry.get("last_sidecast_phase") or "ongoing"
                    detail_parts.append(f"sidecast {sidecast} ({phase})")
                summary = "; ".join(detail_parts) if detail_parts else "relationship"
                lines.append(f" - {entry['scholar']} (Δ {feeling_text}) — {summary}")
        sentiments = data.get("faction_sentiments") or {}
        if sentiments:
            lines.append("")
            lines.append("Faction Sentiment:")
            for faction, payload in sorted(sentiments.items()):
                avg = payload.get("average", 0.0)
                count = payload.get("count", 0)
                label = faction.capitalize()
                lines.append(
                    " - {faction}: Δ {avg:+.2f} ({count} scholar{plural})".format(
                        faction=label,
                        avg=avg,
                        count=count,
                        plural="s" if count != 1 else "",
                    )
                )
        commitments = data.get("commitments") or []
        if commitments:
            lines.append("")
            lines.append("Seasonal Commitments:")
            for entry in commitments:
                relationship_pct = entry.get("relationship_modifier", 0.0) * 100
                end_at = entry.get("end_at")
                if isinstance(end_at, datetime):
                    end_text = end_at.strftime("%Y-%m-%d")
                else:
                    end_text = str(end_at) if end_at else "ongoing"
                lines.append(
                    " - {faction}: status {status}, Δ {rel:+.1f}%, ends {end}".format(
                        faction=(entry.get("faction") or "Unaligned").capitalize(),
                        status=entry.get("status", "active"),
                        rel=relationship_pct,
                        end=end_text,
                    )
                )
        investments = data.get("investments") or []
        if investments:
            lines.append("")
            lines.append("Faction Investments:")
            for entry in investments:
                faction = (entry.get("faction") or "Unaligned").capitalize()
                latest = entry.get("latest") or "—"
                lines.append(
                    " - {faction}: total {total} influence across {count} contribution(s); latest {latest}".format(
                        faction=faction,
                        total=entry.get("total", 0),
                        count=entry.get("count", 0),
                        latest=latest,
                    )
                )
                programs = entry.get("programs") or []
                if programs:
                    lines.append("   Programs: " + ", ".join(programs))
        endowments = data.get("endowments") or []
        if endowments:
            lines.append("")
            lines.append("Archive Endowments:")
            for entry in endowments:
                faction = (entry.get("faction") or "Unaligned").capitalize()
                latest = entry.get("latest") or "—"
                lines.append(
                    " - {faction}: total {total} donated across {count} gift(s); latest {latest}".format(
                        faction=faction,
                        total=entry.get("total", 0),
                        count=entry.get("count", 0),
                        latest=latest,
                    )
                )
                programs = entry.get("programs") or []
                if programs:
                    lines.append("   Initiatives: " + ", ".join(programs))
        header = f"**/status requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="status",
            header=header,
            ephemeral=True,
        )

    @app_commands.command(name="invest", description="Invest influence into faction infrastructure")
    @track_command
    @app_commands.describe(
        faction="Faction receiving the investment",
        amount="Influence to invest",
        program="Optional program label for record keeping",
    )
    async def invest(
        interaction: discord.Interaction,
        faction: str,
        amount: int,
        program: Optional[str] = None,
    ) -> None:
        player_id = str(interaction.user.display_name)
        service.ensure_player(player_id, interaction.user.display_name)
        try:
            press = service.invest_in_faction(
                player_id=player_id,
                faction=faction.lower(),
                amount=amount,
                program=program,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.gazette, message, purpose="investment")
        await _flush_admin_notifications()

    @app_commands.command(name="endow_archive", description="Donate influence to the public archive")
    @track_command
    @app_commands.describe(
        amount="Influence to donate",
        faction="Faction pool to draw from (defaults to academia)",
        program="Optional endowment name",
    )
    async def endow_archive(
        interaction: discord.Interaction,
        amount: int,
        faction: Optional[str] = None,
        program: Optional[str] = None,
    ) -> None:
        player_id = str(interaction.user.display_name)
        service.ensure_player(player_id, interaction.user.display_name)
        try:
            press = service.endow_archive(
                player_id=player_id,
                amount=amount,
                faction=faction.lower() if faction else None,
                program=program,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.gazette, message, purpose="endowment")
        await _flush_admin_notifications()

    @app_commands.command(name="wager", description="Show the confidence wager table and thresholds")
    @track_command
    async def wager(interaction: discord.Interaction) -> None:
        reference = service.wager_reference()
        lines = ["**Confidence Wagers Reference**", "Confidence wagers:"]
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
        header = f"**/wager requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="wager-reference",
            header=header,
            ephemeral=True,
        )

    @app_commands.command(name="seasonal_commitments", description="View your seasonal commitments")
    @track_command
    async def seasonal_commitments(interaction: discord.Interaction) -> None:
        player_id = str(interaction.user.display_name)
        service.ensure_player(player_id, interaction.user.display_name)
        commitments = service.list_seasonal_commitments(player_id)
        if not commitments:
            await interaction.response.send_message("No seasonal commitments recorded.", ephemeral=True)
            return
        lines = ["**Seasonal Commitments**"]
        for entry in commitments:
            faction = (entry.get("faction") or "Unaligned").capitalize()
            status = entry.get("status", "active")
            end_at = entry.get("end_at")
            if isinstance(end_at, datetime):
                end_text = end_at.strftime("%Y-%m-%d")
            else:
                end_text = str(end_at) if end_at else "ongoing"
            lines.append(
                "• {faction}: status {status}, base cost {cost}, ends {end}".format(
                    faction=faction,
                    status=status,
                    cost=entry.get("base_cost", 0),
                    end=end_text,
                )
            )
        header = f"**/seasonal_commitments requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="seasonal-commitments",
            header=header,
            ephemeral=True,
        )

    @app_commands.command(name="faction_projects", description="Show active faction projects")
    @track_command
    async def faction_projects(interaction: discord.Interaction) -> None:
        projects = service.list_faction_projects()
        if not projects:
            await interaction.response.send_message("No active faction projects.", ephemeral=True)
            return
        lines = ["**Active Faction Projects**"]
        for project in projects:
            progress = project.get("progress", 0.0)
            target = project.get("target_progress", 0.0)
            progress_pct = (progress / target * 100) if target else 0
            lines.append(
                "• {name} ({faction}) — {progress:.2f}/{target:.2f} ({pct:.1f}%)".format(
                    name=project.get("name", "Project"),
                    faction=(project.get("faction") or "Unaligned").capitalize(),
                    progress=progress,
                    target=target,
                    pct=progress_pct,
                )
            )
        header = f"**/faction_projects requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="faction-projects",
            header=header,
            ephemeral=True,
        )

    @app_commands.command(name="gazette", description="Show recent Gazette headlines")
    @track_command
    async def gazette(interaction: discord.Interaction, limit: int = 5) -> None:
        if limit <= 0 or limit > 20:
            await interaction.response.send_message("Limit must be between 1 and 20", ephemeral=True)
            return
        records = service.export_press_archive(limit=limit)
        if not records:
            await interaction.response.send_message("No Gazette entries recorded yet.", ephemeral=True)
            return
        lines = ["**Recent Gazette Entries**"]
        for record in records:
            timestamp = record.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f" - {timestamp} | {record.release.headline}")
        header = f"**/gazette requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="gazette-summary",
            header=header,
            ephemeral=True,
        )

    @app_commands.command(name="export_log", description="Export recent events and press")
    @track_command
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
        lines = ["**Archive Log Extract**"] + press_lines + [""] + event_lines
        header = f"**/export_log requested by {interaction.user.display_name}**"
        await _respond_and_broadcast(
            interaction,
            lines,
            purpose="export-log",
            header=header,
            ephemeral=True,
        )
        await _flush_admin_notifications()

    @app_commands.command(name="export_web_archive", description="Generate static HTML archive of game history")
    @track_command
    async def export_web_archive(interaction: discord.Interaction) -> None:
        """Export the complete game history as a static web archive."""
        await interaction.response.defer(ephemeral=True)
        try:
            output_path = service.export_web_archive(source="command")

            # Count files and get stats
            press_count = len(list(service.state.list_press_releases()))
            scholar_count = len(list(service.state.all_scholars()))

            message = (
                f"**Web Archive Generated Successfully!**\n\n"
                f"📁 Location: `{output_path.absolute()}`\n"
                f"📰 Press Releases: {press_count}\n"
                f"🎓 Scholar Profiles: {scholar_count}\n\n"
                f"The archive includes:\n"
                f"• Individual pages for each press release with permalinks\n"
                f"• Scholar profile pages with memories and relationships\n"
                f"• Chronological timeline of events\n"
                f"• Search and filter functionality\n\n"
                f"Open `{output_path}/index.html` in a browser to view."
            )
            await interaction.followup.send(message, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error generating archive: {e}", ephemeral=True)
        await _flush_admin_notifications()

    @app_commands.command(name="archive_link", description="Get web archive permalink for a press release")
    @track_command
    async def archive_link(interaction: discord.Interaction, headline_search: str) -> None:
        """Return permalink for specific press release matching the search term."""
        from .web_archive import WebArchive
        from pathlib import Path

        # Search for matching press releases
        all_press = service.state.list_press_releases_with_ids()
        matches: List[tuple[int, PressRecord]] = []

        for press_id, record in all_press:
            if headline_search.lower() in record.release.headline.lower():
                matches.append((press_id, record))

        if not matches:
            await interaction.response.send_message(
                f"No press releases found matching '{headline_search}'",
                ephemeral=True
            )
            await _flush_admin_notifications()
            return

        # Generate permalinks for matches
        archive = WebArchive(service.state, Path("web_archive"))

        if len(matches) == 1:
            press_id, record = matches[0]
            permalink = archive.generate_permalink(record)
            message = (
                f"**Found Press Release:**\n"
                f"Headline: {record.release.headline}\n"
                f"Date: {record.timestamp.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Permalink: `{permalink}`\n"
                f"Press ID: #{press_id}"
            )
        else:
            # Multiple matches - show first 5
            lines = [f"**Found {len(matches)} matching press releases:**\n"]
              
            for press_id, record in matches[:5]:
                permalink = archive.generate_permalink(record)
                lines.append(
                    f"• {record.release.headline}\n"
                    f"  Date: {record.timestamp.strftime('%Y-%m-%d')}\n"
                    f"  Permalink: `{permalink}`\n"
                    f"  Press ID: #{press_id}\n"
                )
            if len(matches) > 5:
                lines.append(f"\n...and {len(matches) - 5} more matches")
            message = "\n".join(lines)

        telemetry = get_telemetry()
        try:
            telemetry.track_game_progression(
                "archive_lookup",
                1.0,
                player_id=str(interaction.user.id),
                details={
                    "search": headline_search,
                    "matches": len(matches),
                    "single_match": len(matches) == 1,
                },
            )
        except Exception:  # pragma: no cover - telemetry must not block responses
            logger.debug("Failed to record archive lookup telemetry", exc_info=True)

        await interaction.response.send_message(message, ephemeral=True)
        await _flush_admin_notifications()

    @app_commands.command(name="telemetry_report", description="View telemetry and usage statistics (admin only)")
    @track_command
    async def telemetry_report(interaction: discord.Interaction) -> None:
        """Generate and display telemetry report."""
        # Check for admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "This command requires administrator permissions.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            telemetry = get_telemetry()
            telemetry.flush()  # Ensure all buffered metrics are saved
            report = telemetry.generate_report()

            # Format report for Discord
            lines = [
                "**📊 Telemetry Report**",
                f"Generated: {report['generated_at']}",
                f"Uptime: {report['uptime_seconds'] / 3600:.1f} hours\n",
                "**Overall Statistics:**",
                f"• Total events: {report['overall']['total_events']:,}",
                f"• Unique players: {report['overall']['unique_players']}",
            ]

            health = report.get('health', {})
            checks = health.get('checks', [])
            if checks:
                lines.append("\n**Health Summary:**")
                status_icons = {"ok": "✅", "warning": "⚠️", "alert": "🛑"}
                for check in checks[:6]:
                    icon = status_icons.get(check.get('status'), "•")
                    label = check.get('label', check.get('metric', 'metric'))
                    detail = check.get('detail', '')
                    lines.append(f"{icon} {label}: {detail}")
                if len(checks) > 6:
                    lines.append(f"…plus {len(checks) - 6} more checks")

            product = report.get('product_kpis', {})
            if product:
                engagement = product.get('engagement', {})
                manifestos = product.get('manifestos', {})
                archive = product.get('archive', {})
                nicknames = product.get('nicknames', {})
                shares = product.get('press_shares', {})
                lines.append("\n**Product KPIs:**")
                lines.append(
                    "• Active players (24h): {players:.0f} | Avg cmds/player {avg:.1f}".format(
                        players=engagement.get('active_players_24h', 0.0) or 0.0,
                        avg=engagement.get('avg_commands_per_player_24h', 0.0) or 0.0,
                    )
                )
                lines.append(
                    "• Active players (7d): {players:.0f} | Avg cmds/player {avg:.1f}".format(
                        players=engagement.get('active_players_7d', 0.0) or 0.0,
                        avg=engagement.get('avg_commands_per_player_7d', 0.0) or 0.0,
                    )
                )
                adoption_rate = manifestos.get('adoption_rate_7d', 0.0) or 0.0
                lines.append(
                    "• Manifesto adoption (7d): {rate:.0%} — {players:.0f} player(s), {events:.0f} events".format(
                        rate=adoption_rate,
                        players=manifestos.get('manifesto_players_7d', 0.0) or 0.0,
                        events=manifestos.get('manifesto_events_7d', 0.0) or 0.0,
                    )
                )
                archive_share = archive.get('engaged_share_7d', 0.0) or 0.0
                lines.append(
                    "• Archive lookups (7d): {events:.0f} — {players:.0f} player(s), reach {share:.0%}".format(
                        events=archive.get('lookup_events_7d', 0.0) or 0.0,
                        players=archive.get('lookup_players_7d', 0.0) or 0.0,
                        share=archive_share,
                    )
                )
                lines.append(
                    "• Nicknames (7d): {events:.0f} events by {players:.0f} player(s) ({rate:.0%} adoption)".format(
                        events=nicknames.get('nickname_events_7d', 0.0) or 0.0,
                        players=nicknames.get('nickname_players_7d', 0.0) or 0.0,
                        rate=nicknames.get('nickname_rate_7d', 0.0) or 0.0,
                    )
                )
                lines.append(
                    "• Press shares (7d): {events:.0f} shares by {players:.0f} player(s)".format(
                        events=shares.get('press_shares_7d', 0.0) or 0.0,
                        players=shares.get('press_share_players_7d', 0.0) or 0.0,
                    )
                )

            history_block = report.get('product_kpi_history', {}).get('daily', [])
            history_summary = report.get('product_kpi_history', {}).get('summary', {})
            if history_block:
                lines.append("\n**KPI Trend (last 7 days):**")
                for entry in history_block[-7:]:
                    lines.append(
                        "• {date}: players {players:.0f}, manifestos {m_events:.0f}, archive {a_events:.0f}, nicknames {n_events:.0f}, shares {s_events:.0f}".format(
                            date=entry.get('date', '—'),
                            players=entry.get('active_players', 0.0) or 0.0,
                            m_events=entry.get('manifesto_events', 0.0) or 0.0,
                            a_events=entry.get('archive_events', 0.0) or 0.0,
                            n_events=entry.get('nickname_events', 0.0) or 0.0,
                            s_events=entry.get('press_share_events', 0.0) or 0.0,
                        )
                    )
                if history_summary:
                    lines.append(
                        "• 30d averages — players {players:.1f}, manifestos {manif:.1f}, archive {archive:.1f}, nicknames {nick:.1f}, shares {share:.1f}".format(
                            players=history_summary.get('active_players', {}).get('average', 0.0),
                            manif=history_summary.get('manifesto_events', {}).get('average', 0.0),
                            archive=history_summary.get('archive_events', {}).get('average', 0.0),
                            nick=history_summary.get('nickname_events', {}).get('average', 0.0),
                            share=history_summary.get('press_share_events', {}).get('average', 0.0),
                        )
                    )

            # Command usage
            if report['command_stats']:
                lines.append("\n**Command Usage:**")
                for cmd, stats in sorted(report['command_stats'].items(), key=lambda x: x[1]['usage_count'], reverse=True)[:10]:
                    lines.append(f"• /{cmd}: {stats['usage_count']} uses, {stats['success_rate']:.0%} success")

            # Feature engagement
            if report['feature_engagement_7d']:
                lines.append("\n**Feature Engagement (7 days):**")
                for feature, stats in sorted(report['feature_engagement_7d'].items(), key=lambda x: x[1]['total_uses'], reverse=True)[:5]:
                    lines.append(f"• {feature}: {stats['total_uses']} uses by {stats['unique_users']} players")

            # Recent errors
            if report['errors_24h']:
                lines.append("\n**Errors (24 hours):**")
                for error_type, count in sorted(report['errors_24h'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    lines.append(f"• {error_type}: {count} occurrences")

            # Performance
            if report['performance_1h']:
                lines.append("\n**Performance (1 hour):**")
                for op, perf in sorted(report['performance_1h'].items(), key=lambda x: x[1]['avg_duration_ms'], reverse=True)[:5]:
                    lines.append(f"• {op}: avg {perf['avg_duration_ms']:.1f}ms ({perf['sample_count']} samples)")

            channel_usage = report.get('channel_usage_24h', {})
            if channel_usage:
                lines.append("\n**Channel Usage (24 hours):**")
                for channel_id, stats in sorted(channel_usage.items(), key=lambda x: x[1]['usage_count'], reverse=True)[:5]:
                    if channel_id.isdigit() and interaction.guild:
                        channel_obj = interaction.guild.get_channel(int(channel_id))
                        if channel_obj:
                            channel_label = f"#{channel_obj.name}"
                        else:
                            channel_label = f"<#{channel_id}>"
                    elif channel_id == "dm":
                        channel_label = "Direct Messages"
                    elif channel_id == "unknown":
                        channel_label = "Unknown"
                    else:
                        channel_label = channel_id

                    lines.append(
                        "• {channel}: {count} cmds, {players} players, {cmds} unique commands".format(
                            channel=channel_label,
                            count=stats['usage_count'],
                            players=stats['unique_players'],
                            cmds=stats['unique_commands'],
                        )
                    )

            llm_stats = report.get('llm_activity_24h', {})
            if llm_stats:
                lines.append("\n**LLM Activity (24 hours):**")
                for press_type, stats in sorted(llm_stats.items(), key=lambda x: x[1]['total_calls'], reverse=True)[:5]:
                    success_rate = stats['success_rate'] * 100
                    lines.append(
                        "• {press}: {succ}/{total} success ({rate:.0f}%), avg {avg:.0f}ms, max {max:.0f}ms".format(
                            press=press_type.replace('_', ' '),
                            succ=stats['successes'],
                            total=stats['total_calls'],
                            rate=success_rate,
                            avg=stats['avg_duration_ms'],
                            max=stats['max_duration_ms'],
                        )
                    )

            press_layers = report.get('press_cadence_24h', [])
            if press_layers:
                lines.append("\n**Press Cadence (24 hours):**")
                for entry in press_layers:
                    lines.append(
                        "• {event}/{layer}: {count} layers, avg {avg:.0f}m delay (max {max:.0f}m)".format(
                            event=entry.get('event_type', 'event'),
                            layer=entry.get('layer_type', 'layer'),
                            count=entry.get('layer_count', 0),
                            avg=entry.get('avg_delay_minutes', 0.0),
                            max=entry.get('max_delay_minutes', 0.0),
                        )
                    )

            digest_stats = report.get('digest_health_24h', {})
            if digest_stats and digest_stats.get('total_digests', 0) > 0:
                lines.append("\n**Digest Health (24 hours):**")
                lines.append(
                    "• Avg runtime {avg:.0f}ms (max {max:.0f}ms) across {count} digests".format(
                        avg=digest_stats.get('avg_duration_ms', 0.0),
                        max=digest_stats.get('max_duration_ms', 0.0),
                        count=digest_stats.get('total_digests', 0),
                    )
                )
                lines.append(
                    "• Avg releases {avg_rel:.1f} (max {max_rel}) — Queue avg {avg_q:.1f} pending (max {max_q})".format(
                        avg_rel=digest_stats.get('avg_release_count', 0.0),
                        max_rel=digest_stats.get('max_release_count', 0),
                        avg_q=digest_stats.get('avg_queue_size', 0.0),
                        max_q=digest_stats.get('max_queue_size', 0),
                    )
                )

            queue_summary = report.get('queue_depth_24h', {})
            if queue_summary:
                lines.append("\n**Queue Depth (24 hours):**")
                for horizon, stats in sorted(queue_summary.items(), key=lambda item: int(item[0])):
                    lines.append(
                        "• ≤{h}h: avg {avg:.1f}, max {max:.0f} (samples {count})".format(
                            h=horizon,
                            avg=stats.get('avg_queue', 0.0),
                            max=stats.get('max_queue', 0.0),
                            count=int(stats.get('samples', 0)),
                        )
                    )
                threshold = os.getenv("GREAT_WORK_ALERT_MAX_QUEUE")
                if threshold:
                    lines.append(
                        f"• Alert threshold: {threshold} pending items"
                    )

            backlog_summary = report.get('order_backlog_24h', {})
            if backlog_summary:
                lines.append("\n**Dispatcher Backlog (24 hours):**")
                ordered = sorted(
                    backlog_summary.items(),
                    key=lambda item: item[1].get('latest_pending', 0.0),
                    reverse=True,
                )
                for order_type, stats in ordered[:5]:
                    latest = stats.get('latest_pending', 0.0)
                    max_pending = stats.get('max_pending', 0.0)
                    oldest_hours = stats.get('latest_oldest_seconds', 0.0) / 3600.0
                    lines.append(
                        "• {otype}: {latest:.0f} pending (max {max_pending:.0f}), oldest {oldest:.1f}h".format(
                            otype=order_type.replace('_', ' '),
                            latest=latest,
                            max_pending=max_pending,
                            oldest=oldest_hours,
                        )
                    )

            symposium_metrics = report.get('symposium', {})
            scoring_metrics = symposium_metrics.get('scoring', {})
            if scoring_metrics.get('count'):
                lines.append("\n**Symposium Scoring (24 hours):**")
                lines.append(
                    "• {count} proposals scored | avg {avg:.2f}".format(
                        count=scoring_metrics.get('count', 0),
                        avg=scoring_metrics.get('average', 0.0),
                    )
                )
                for entry in scoring_metrics.get('top', [])[:5]:
                    player_name = entry.get('player_id') or 'unknown'
                    player_obj = service.state.get_player(player_name)
                    display = player_obj.display_name if player_obj else player_name
                    lines.append(
                        "• {player} — {score:.2f} (age {age:.1f}d)".format(
                            player=display,
                            score=entry.get('score', 0.0),
                            age=entry.get('age_days', 0.0),
                        )
                    )

            debt_metrics = symposium_metrics.get('debts', [])
            if debt_metrics:
                lines.append("\n**Symposium Debt Snapshot:**")
                for entry in debt_metrics[:5]:
                    player_name = entry.get('player_id') or 'unknown'
                    player_obj = service.state.get_player(player_name)
                    display = player_obj.display_name if player_obj else player_name
                    detail_parts = [f"{entry.get('debt', 0.0):.1f} influence"]
                    faction = entry.get('faction') or 'mixed'
                    detail_parts.append(f"faction {faction}")
                    if entry.get('recorded_at'):
                        detail_parts.append(f"recorded {entry['recorded_at']}")
                    lines.append(
                        "• {player}: {detail}".format(
                            player=display,
                            detail=", ".join(detail_parts),
                        )
                    )

            reprisal_metrics = symposium_metrics.get('reprisals', [])
            if reprisal_metrics:
                lines.append("\n**Symposium Reprisals (24 hours):**")
                for entry in reprisal_metrics[:5]:
                    player_name = entry.get('player_id') or 'unknown'
                    player_obj = service.state.get_player(player_name)
                    display = player_obj.display_name if player_obj else player_name
                    lines.append(
                        "• {player}: {count} reprisal(s), total penalty {penalty:.1f}".format(
                            player=display,
                            count=entry.get('count', 0),
                            penalty=entry.get('total_penalty', 0.0),
                        )
                    )

            economy_metrics = report.get('economy', {})
            if economy_metrics:
                invest = economy_metrics.get('investments', {})
                endow = economy_metrics.get('endowments', {})
                commitments = economy_metrics.get('commitments', {})
                lines.append("\n**Long-tail Economy (24 hours):**")
                lines.append(
                    "• Investments: {total:.1f} influence across {players} player(s)".format(
                        total=invest.get('total_amount', 0.0),
                        players=invest.get('unique_players', 0),
                    )
                )
                if invest.get('top_players'):
                    top_investor = invest['top_players'][0]
                    lines.append(
                        "• Top investor {player} — {amount:.1f} influence (share {share:.0%})".format(
                            player=top_investor.get('player_id', 'unknown'),
                            amount=top_investor.get('total', 0.0),
                            share=invest.get('top_share', 0.0),
                        )
                    )
                if invest.get('by_faction'):
                    faction_parts = [
                        f"{f}:{amount:.1f}"
                        for f, amount in sorted(invest['by_faction'].items(), key=lambda item: item[1], reverse=True)[:3]
                    ]
                    lines.append("• By faction: " + ", ".join(faction_parts))
                lines.append(
                    "• Archive endowments: {total:.1f} influence (debt paid {debt:.1f}, reputation +{rep:.1f})".format(
                        total=endow.get('total_amount', 0.0),
                        debt=endow.get('total_debt_paid', 0.0),
                        rep=endow.get('total_reputation_gain', 0.0),
                    )
                )
                if endow.get('top_players'):
                    top_endower = endow['top_players'][0]
                    lines.append(
                        "• Largest endowment {player}: {amount:.1f} influence".format(
                            player=top_endower.get('player_id', 'unknown'),
                            amount=top_endower.get('total', 0.0),
                        )
                    )
                if commitments:
                    outstanding = commitments.get('total_outstanding', 0.0)
                    lines.append(
                        "• Seasonal commitments outstanding: {debt:.1f} influence".format(
                            debt=outstanding,
                        )
                    )
                    top_commitments = sorted(
                        commitments.get('players', {}).values(),
                        key=lambda item: item.get('latest_debt', 0.0),
                        reverse=True,
                    )[:3]
                    for entry in top_commitments:
                        player_label = entry.get('player_id') or 'unknown'
                        debt_val = entry.get('latest_debt', 0.0)
                        faction_label = entry.get('faction') or 'unaligned'
                        days_remaining = entry.get('days_remaining')
                        descriptor = f"{debt_val:.1f} owed to {faction_label}"
                        if days_remaining is not None:
                            descriptor += f", {int(days_remaining)}d remaining"
                        lines.append(f"   • {player_label}: {descriptor}")

            system_events = report.get('system_events_24h', [])
            if system_events:
                lines.append("\n**System Events (24 hours):**")
                for event in system_events[:5]:
                    detail = f" — {event['reason']}" if event.get('reason') else ""
                    lines.append(f"• {event['timestamp']}: {event['event']}{detail}")

            message = "\n".join(lines)

            # Split message if too long
            if len(message) > 2000:
                message = message[:1997] + "..."

            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Error generating report: {e}", ephemeral=True)

    @app_commands.command(name="table_talk", description="Post a message to the table-talk channel")
    @track_command
    async def table_talk(interaction: discord.Interaction, message: str) -> None:
        display_name = interaction.user.display_name
        if router.table_talk is None:
            await interaction.response.send_message(
                "Table-talk channel is not configured.",
                ephemeral=True,
            )
            return
        try:
            press = service.post_table_talk(
                player_id=str(interaction.user.display_name),
                display_name=display_name,
                message=message,
            )
        except GameService.ModerationRejectedError as exc:
            await interaction.response.send_message(
                f"Moderation blocked that message: {exc}",
                ephemeral=True,
            )
            await _flush_admin_notifications()
            return
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        formatted = _format_press(press)
        await _post_to_channel(bot, router.table_talk, formatted, purpose="table-talk")
        await interaction.response.send_message("Posted to table-talk.", ephemeral=True)
        await _flush_admin_notifications()

    # Admin command group
    gw_admin = app_commands.Group(
        name="gw_admin",
        description="Administrative commands for game management"
    )

    @gw_admin.command(name="adjust_reputation", description="Adjust a player's reputation")
    @track_command
    @app_commands.describe(
        player_id="Player identifier",
        delta="Reputation change amount",
        reason="Reason for adjustment",
    )
    async def admin_reputation(
        interaction: discord.Interaction,
        player_id: str,
        delta: int,
        reason: str,
    ) -> None:
        # Check for admin role (simplified - you may want proper role checking)
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_adjust_reputation(
                admin_id=admin_id,
                player_id=player_id,
                delta=delta,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.gazette, message, purpose="admin action")
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        await _flush_admin_notifications()
        return
    await _flush_admin_notifications()

    @gw_admin.command(
        name="create_seasonal_commitment",
        description="Create a seasonal commitment for a player",
    )
    @track_command
    @app_commands.describe(
        player_id="Player identifier",
        faction="Faction name",
        tier="Optional tier label",
        base_cost="Optional base cost override",
        duration_days="Optional duration override",
        reason="Optional note for the change",
    )
    async def admin_create_commitment(
        interaction: discord.Interaction,
        player_id: str,
        faction: str,
        tier: Optional[str] = None,
        base_cost: Optional[int] = None,
        duration_days: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_create_seasonal_commitment(
                admin_id=admin_id,
                player_id=player_id,
                faction=faction,
                tier=tier,
                base_cost=base_cost,
                duration_days=duration_days,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(
        name="update_seasonal_commitment",
        description="Cancel or complete a seasonal commitment",
    )
    @track_command
    @app_commands.describe(
        commitment_id="Commitment identifier",
        reason="Optional note for the update",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Completed", value="completed"),
            app_commands.Choice(name="Cancelled", value="cancelled"),
        ]
    )
    async def admin_update_commitment(
        interaction: discord.Interaction,
        commitment_id: int,
        status: app_commands.Choice[str],
        reason: Optional[str] = None,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_update_seasonal_commitment(
                admin_id=admin_id,
                commitment_id=commitment_id,
                status=status.value,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(
        name="create_faction_project",
        description="Create a faction project",
    )
    @track_command
    @app_commands.describe(
        name="Project name",
        faction="Faction name",
        target_progress="Target progress value",
        reason="Optional note for the change",
    )
    async def admin_create_project(
        interaction: discord.Interaction,
        name: str,
        faction: str,
        target_progress: float,
        reason: Optional[str] = None,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_create_faction_project(
                admin_id=admin_id,
                name=name,
                faction=faction,
                target_progress=target_progress,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(
        name="update_faction_project",
        description="Cancel or complete a faction project",
    )
    @track_command
    @app_commands.describe(
        project_id="Project identifier",
        reason="Optional note for the update",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Completed", value="completed"),
            app_commands.Choice(name="Cancelled", value="cancelled"),
        ]
    )
    async def admin_update_project(
        interaction: discord.Interaction,
        project_id: int,
        status: app_commands.Choice[str],
        reason: Optional[str] = None,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_update_faction_project(
                admin_id=admin_id,
                project_id=project_id,
                status=status.value,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(name="adjust_influence", description="Adjust a player's influence")
    @track_command
    @app_commands.describe(
        player_id="Player identifier",
        faction="Faction name",
        delta="Influence change amount",
        reason="Reason for adjustment",
    )
    async def admin_influence(
        interaction: discord.Interaction,
        player_id: str,
        faction: str,
        delta: int,
        reason: str,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_adjust_influence(
                admin_id=admin_id,
                player_id=player_id,
                faction=faction,
                delta=delta,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(name="force_defection", description="Force a scholar to defect")
    @track_command
    @app_commands.describe(
        scholar_id="Scholar identifier",
        new_faction="New faction for the scholar",
        reason="Reason for forced defection",
    )
    async def admin_defection(
        interaction: discord.Interaction,
        scholar_id: str,
        new_faction: str,
        reason: str,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_force_defection(
                admin_id=admin_id,
                scholar_id=scholar_id,
                new_faction=new_faction,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(name="cancel_expedition", description="Cancel a pending expedition")
    @track_command
    @app_commands.describe(
        expedition_code="Expedition code",
        reason="Reason for cancellation",
    )
    async def admin_cancel(
        interaction: discord.Interaction,
        expedition_code: str,
        reason: str,
    ) -> None:
        admin_id = str(interaction.user.display_name)
        try:
            press = service.admin_cancel_expedition(
                admin_id=admin_id,
                expedition_code=expedition_code,
                reason=reason,
            )
            message = f"{press.headline}\n{press.body}"
            await interaction.response.send_message(message)
            await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return
        await _flush_admin_notifications()

    @gw_admin.command(name="list_orders", description="List dispatcher orders")
    @track_command
    @app_commands.describe(
        order_type="Filter by order type (e.g. followup:symposium_reprimand)",
        status="Order status filter (pending/completed/cancelled/any)",
        limit="Maximum number of rows to display (1-50)",
        actor_id="Only include orders with this actor id",
        subject_id="Only include orders with this subject id",
        older_than_hours="Only include orders older than this many hours",
        include_payload="Append JSON payload details",
        as_file="Attach the results as a text file",
    )
    async def admin_list_orders(
        interaction: discord.Interaction,
        order_type: Optional[str] = None,
        status: Optional[str] = "pending",
        limit: int = 10,
        actor_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        older_than_hours: Optional[float] = None,
        include_payload: bool = False,
        as_file: bool = False,
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "This command requires administrator permissions.",
                ephemeral=True,
            )
            return

        limit = max(1, min(limit, 50))
        status_filter = None if not status or status.lower() == "any" else status.lower()
        orders = service.admin_list_orders(
            order_type=order_type or None,
            status=status_filter,
            limit=limit,
        )

        if actor_id:
            orders = [order for order in orders if (order.get("actor_id") or "") == actor_id]
        if subject_id:
            orders = [order for order in orders if (order.get("subject_id") or "") == subject_id]

        if older_than_hours is not None and older_than_hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

            def _order_timestamp(order: Dict[str, object]) -> Optional[datetime]:
                scheduled = order.get("scheduled_at")
                if isinstance(scheduled, datetime):
                    return scheduled
                created = order.get("created_at")
                if isinstance(created, datetime):
                    return created
                return None

            filtered_orders: List[Dict[str, object]] = []
            for order in orders:
                reference = _order_timestamp(order)
                if reference is not None and reference <= cutoff:
                    filtered_orders.append(order)
            orders = filtered_orders

        if not orders:
            await interaction.response.send_message("No dispatcher orders found.", ephemeral=True)
            return

        now_ts = datetime.now(timezone.utc)
        lines = ["#id | type | status | actor | subject | age(h) | scheduled | created"]
        for order in orders:
            scheduled = order.get("scheduled_at")
            created = order.get("created_at")
            scheduled_label = scheduled.isoformat() if isinstance(scheduled, datetime) else "—"
            created_label = created.isoformat() if isinstance(created, datetime) else "—"
            reference = scheduled if isinstance(scheduled, datetime) else created
            if isinstance(reference, datetime):
                age_hours = max(0.0, (now_ts - reference).total_seconds() / 3600.0)
            else:
                age_hours = 0.0
            line = (
                f"#{order['id']} | {order.get('order_type', 'unknown')} | {order.get('status', '?')} | "
                f"{order.get('actor_id') or '—'} | {order.get('subject_id') or '—'} | {age_hours:.1f} | "
                f"{scheduled_label} | {created_label}"
            )
            lines.append(line)
            if include_payload:
                payload = order.get("payload") or {}
                payload_json = json.dumps(payload, sort_keys=True)
                lines.append(f"  payload: {payload_json}")

        content = "\n".join(lines)
        send_as_file = as_file or len(content) > 1900
        summary_line = f"Returned {len(orders)} orders" + (f" (filtered by {order_type})" if order_type else "")

        if send_as_file:
            buffer = io.BytesIO(content.encode("utf-8"))
            buffer.seek(0)
            file_name = "orders_report.txt"
            await interaction.response.send_message(
                summary_line,
                file=discord.File(buffer, filename=file_name),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(f"```
{content}
```", ephemeral=True)
        await _flush_admin_notifications()

    @gw_admin.command(name="cancel_order", description="Cancel a dispatcher order")
    @track_command
    @app_commands.describe(
        order_id="Numeric identifier of the dispatcher order",
        reason="Optional reason for cancellation",
    )
    async def admin_cancel_order(
        interaction: discord.Interaction,
        order_id: int,
        reason: Optional[str] = None,
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "This command requires administrator permissions.",
                ephemeral=True,
            )
            return

        try:
            summary = service.admin_cancel_order(order_id=order_id, reason=reason)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            await _flush_admin_notifications()
            return

        response = (
            f"Cancelled order #{summary['id']} ({summary['order_type']})."
            + (f" Reason: {reason}" if reason else "")
        )
        await interaction.response.send_message(response, ephemeral=True)
        await _flush_admin_notifications()

    @gw_admin.command(
        name="calibration_snapshot",
        description="Generate and upload a calibration snapshot for tuning",
    )
    @track_command
    async def admin_calibration_snapshot(interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "This command requires administrator permissions.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        include_details_env = os.getenv("GREAT_WORK_CALIBRATION_SNAPSHOT_DETAILS", "")
        include_details = include_details_env.lower() not in {"0", "false", "off"}
        snapshot_dir_env = os.getenv("GREAT_WORK_CALIBRATION_SNAPSHOT_DIR", "calibration_snapshots")
        snapshot_dir = Path(snapshot_dir_env).expanduser().resolve()
        keep_env = os.getenv("GREAT_WORK_CALIBRATION_SNAPSHOT_KEEP", "12") or "12"
        try:
            keep_last = max(0, int(keep_env))
        except ValueError:
            keep_last = 12

        telemetry = get_telemetry()
        now = datetime.now(timezone.utc)

        try:
            snapshot = collect_calibration_snapshot(
                service,
                telemetry,
                now=now,
                include_details=include_details,
            )
            output_path = write_calibration_snapshot(
                service,
                telemetry,
                snapshot_dir,
                now=now,
                include_details=include_details,
                keep_last=keep_last,
                snapshot=snapshot,
            )
            file_buffer = io.BytesIO(output_path.read_bytes())
            file_buffer.seek(0)
            upload = discord.File(file_buffer, filename=output_path.name)
            seasonal_totals = snapshot.get("seasonal_commitments", {}).get("totals", {})
            message_lines = [
                f"Calibration snapshot captured at {snapshot.get('generated_at', now.isoformat())}",
                f"Seasonal commitments: {seasonal_totals.get('active', 0)} active / debt {seasonal_totals.get('outstanding_debt', 0)}",
                f"Stored at `{output_path}` (keep_last={keep_last}).",
            ]
            await interaction.followup.send("\n".join(message_lines), file=upload, ephemeral=True)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to generate calibration snapshot")
            await interaction.followup.send(
                f"Failed to generate calibration snapshot: {exc}",
                ephemeral=True,
            )

        await _flush_admin_notifications()

    @gw_admin.command(
        name="pause_game",
        description="Pause the game for maintenance or incident response",
    )
    @track_command
    @app_commands.describe(reason="Optional reason for pausing the game")
    async def admin_pause(
        interaction: discord.Interaction,
        reason: Optional[str] = None,
    ) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "This command requires administrator permissions.",
                ephemeral=True,
            )
            return

        admin_id = str(interaction.user.display_name)
        press = service.pause_game(reason=reason, admin_id=admin_id)
        message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message, ephemeral=True)
        await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        await _flush_admin_notifications()

    @gw_admin.command(name="resume_game", description="Resume the game if it is paused")
    @track_command
    async def admin_resume(interaction: discord.Interaction) -> None:
        admin_id = str(interaction.user.display_name)
        press = service.resume_game(admin_id)
        message = f"{press.headline}\n{press.body}"
        await interaction.response.send_message(message, ephemeral=True)
        await _post_to_channel(bot, router.gazette, message, purpose="admin action")
        await _flush_admin_notifications()
    bot.tree.add_command(submit_theory)
    bot.tree.add_command(launch_expedition)
    bot.tree.add_command(resolve_expeditions)
    bot.tree.add_command(recruit_odds)
    bot.tree.add_command(recruit)
    bot.tree.add_command(mentor)
    bot.tree.add_command(assign_lab)
    bot.tree.add_command(set_nickname)
    bot.tree.add_command(share_press)
    bot.tree.add_command(conference)
    bot.tree.add_command(symposium_vote)
    bot.tree.add_command(symposium_propose)
    bot.tree.add_command(symposium_proposals)
    bot.tree.add_command(symposium_backlog)
    bot.tree.add_command(symposium_status)
    bot.tree.add_command(status)
    bot.tree.add_command(invest)
    bot.tree.add_command(endow_archive)
    bot.tree.add_command(wager)
    bot.tree.add_command(seasonal_commitments)
    bot.tree.add_command(faction_projects)
    bot.tree.add_command(gazette)
    bot.tree.add_command(export_log)
    bot.tree.add_command(export_web_archive)
    bot.tree.add_command(archive_link)
    bot.tree.add_command(table_talk)
    bot.tree.add_command(gw_admin)
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
