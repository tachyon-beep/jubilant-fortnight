"""Discord bot entry point for The Great Work."""
from __future__ import annotations

import atexit
import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .models import ConfidenceLevel, ExpeditionPreparation, PressRelease
from .scheduler import GazetteScheduler
from .service import GameService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelRouter:
    """Configures which Discord channels receive automated posts."""

    orders: Optional[int]
    gazette: Optional[int]
    table_talk: Optional[int]

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
    router = ChannelRouter.from_env()
    scheduler: Optional[GazetteScheduler] = None

    def _shutdown_scheduler() -> None:  # pragma: no cover - process shutdown hook
        if scheduler is not None:
            scheduler.shutdown()

    atexit.register(_shutdown_scheduler)

    @bot.event
    async def on_ready() -> None:
        nonlocal scheduler
        logger.info("Great Work bot connected as %s", bot.user)
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d commands", len(synced))
        except Exception as exc:  # pragma: no cover - logging only
            logger.exception("Failed to sync commands: %s", exc)
        if scheduler is None and router.gazette is not None:
            scheduler = GazetteScheduler(
                service,
                publisher=lambda press: asyncio.run_coroutine_threadsafe(
                    _post_to_channel(
                        bot,
                        router.gazette,
                        _format_press(press),
                        purpose="gazette",
                    ),
                    bot.loop,
                ),
            )
            scheduler.start()
            logger.info("Started Gazette scheduler publishing to %s", router.gazette)

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
        message = _format_press(press)
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")

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
        message = _format_press(press)
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")

    @app_commands.command(name="resolve_expeditions", description="Resolve all pending expeditions")
    async def resolve_expeditions(interaction: discord.Interaction) -> None:
        digest_releases = service.advance_digest()
        releases = digest_releases + service.resolve_pending_expeditions()
        if not releases:
            await interaction.response.send_message("No expeditions waiting.")
            return
        text = "\n\n".join(_format_press(press) for press in releases)
        await interaction.response.send_message(text)
        await _post_to_channel(bot, router.orders, text, purpose="orders")

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
        message = f"{prefix}: {press.headline}\n{press.body}"
        await interaction.response.send_message(message)
        await _post_to_channel(bot, router.orders, message, purpose="orders")

    @app_commands.command(name="mentor", description="Begin mentoring a scholar")
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

    @app_commands.command(name="assign_lab", description="Assign a mentored scholar to a new career track")
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

    @app_commands.command(name="poach", description="Attempt to poach another player's scholar")
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
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @app_commands.command(name="counter", description="Counter a rival's poaching attempt")
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
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @app_commands.command(name="view_offers", description="View active offers involving your scholars")
    async def view_offers(interaction: discord.Interaction) -> None:
        service.ensure_player(str(interaction.user.display_name), interaction.user.display_name)

        try:
            offers = service.list_player_offers(str(interaction.user.display_name))

            if not offers:
                await interaction.response.send_message("No active offers involving you.", ephemeral=True)
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

            await interaction.response.send_message(message, ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"Error: {exc}", ephemeral=True)

    @app_commands.command(name="conference", description="Launch a conference to debate a theory")
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
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @app_commands.command(name="symposium_vote", description="Cast your vote on the current symposium topic")
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

    @app_commands.command(name="export_web_archive", description="Generate static HTML archive of game history")
    async def export_web_archive(interaction: discord.Interaction) -> None:
        """Export the complete game history as a static web archive."""
        await interaction.response.defer(ephemeral=True)
        try:
            from pathlib import Path
            output_path = service.export_web_archive()

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

    @app_commands.command(name="archive_link", description="Get web archive permalink for a press release")
    async def archive_link(interaction: discord.Interaction, headline_search: str) -> None:
        """Return permalink for specific press release matching the search term."""
        from .web_archive import WebArchive
        from pathlib import Path

        # Search for matching press releases
        all_press = list(service.state.list_press_releases())
        matches = []

        for i, record in enumerate(all_press, start=1):
            if headline_search.lower() in record.release.headline.lower():
                matches.append((i, record))

        if not matches:
            await interaction.response.send_message(
                f"No press releases found matching '{headline_search}'",
                ephemeral=True
            )
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
                )
            if len(matches) > 5:
                lines.append(f"\n...and {len(matches) - 5} more matches")
            message = "\n".join(lines)

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="table_talk", description="Post a message to the table-talk channel")
    async def table_talk(interaction: discord.Interaction, message: str) -> None:
        display_name = interaction.user.display_name
        if router.table_talk is None:
            await interaction.response.send_message(
                "Table-talk channel is not configured.",
                ephemeral=True,
            )
            return
        payload = f"**{display_name}:** {message}"
        await _post_to_channel(bot, router.table_talk, payload, purpose="table-talk")
        await interaction.response.send_message("Posted to table-talk.", ephemeral=True)

    # Admin command group
    gw_admin = app_commands.Group(
        name="gw_admin",
        description="Administrative commands for game management"
    )

    @gw_admin.command(name="adjust_reputation", description="Adjust a player's reputation")
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

    @gw_admin.command(name="adjust_influence", description="Adjust a player's influence")
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

    @gw_admin.command(name="force_defection", description="Force a scholar to defect")
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

    @gw_admin.command(name="cancel_expedition", description="Cancel a pending expedition")
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

    bot.tree.add_command(submit_theory)
    bot.tree.add_command(launch_expedition)
    bot.tree.add_command(resolve_expeditions)
    bot.tree.add_command(recruit)
    bot.tree.add_command(mentor)
    bot.tree.add_command(assign_lab)
    bot.tree.add_command(conference)
    bot.tree.add_command(symposium_vote)
    bot.tree.add_command(status)
    bot.tree.add_command(wager)
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
