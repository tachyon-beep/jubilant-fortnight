"""Discord message helpers and formatting utilities.

These helpers are used by the legacy bot entry while we extract Discord-facing
logic into the adapters package.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import discord
from discord.ext import commands

from ...models import PressRelease

logger = logging.getLogger(__name__)


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


async def _post_embed_to_channel(
    bot: commands.Bot,
    channel_id: Optional[int],
    *,
    embed: discord.Embed,
    content: Optional[str],
    purpose: str,
) -> None:
    if channel_id is None:
        logger.debug("Skipping %s embed post; channel not configured", purpose)
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Failed to locate %s channel with id %s", purpose, channel_id)
        return
    try:
        await channel.send(content=content, embed=embed)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to send %s embed", purpose)


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
    lines = [f"**{press.headline}**"]
    metadata = press.metadata or {}
    scheduled = (
        metadata.get("scheduled", {})
        if isinstance(metadata.get("scheduled"), dict)
        else {}
    )
    release_at = scheduled.get("release_at")
    if isinstance(release_at, datetime):  # pragma: no cover - typically stored as str
        release_label = release_at.strftime("%Y-%m-%d %H:%M")
    else:
        release_label = release_at
    if release_label:
        lines.append(f"_Scheduled for {release_label}_")

    source = metadata.get("surface") or metadata.get("type")
    if source:
        lines.append(f"_{source}_")
    lines.append(press.body)
    return "\n".join(lines)


__all__ = [
    "_post_to_channel",
    "_post_embed_to_channel",
    "_post_file_to_channel",
    "_clamp_text",
    "_format_message",
    "_format_press",
    "make_responder",
]


def make_responder(bot: commands.Bot, router) -> "Responder":
    """Factory returning a coroutine to respond and mirror messages.

    The returned function mirrors an initial interaction response to a public
    info channel determined from the router (table_talk → gazette → upcoming → orders).
    """

    def _info_channel() -> Optional[int]:
        return router.table_talk or router.gazette or router.upcoming or router.orders

    async def _respond_and_broadcast(
        interaction: discord.Interaction,
        lines: Optional[Iterable[str]] = None,
        *,
        purpose: str,
        header: Optional[str] = None,
        channel: Optional[int] = None,
        ephemeral: bool = True,
        embed: Optional[discord.Embed] = None,
    ) -> None:
        if embed is not None and lines is None:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            message = _format_message(lines or [])
            await interaction.response.send_message(message, ephemeral=ephemeral)

        target_channel = channel if channel is not None else _info_channel()
        if target_channel is None:
            return

        if embed is not None and lines is None:
            public_embed = embed.copy()
            content = header or None
            await _post_embed_to_channel(
                bot, target_channel, embed=public_embed, content=content, purpose=purpose
            )
            return

        public_message = _format_message(lines or [])
        if header:
            public_message = _clamp_text(f"{header}\n{public_message}")
        if not public_message.strip():
            return
        await _post_to_channel(bot, target_channel, public_message, purpose=purpose)

    return _respond_and_broadcast
