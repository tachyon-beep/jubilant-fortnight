"""Discord command telemetry decorator."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

import discord

from .telemetry import get_telemetry


def track_command(func: Callable) -> Callable:
    """Decorator to track Discord command usage and performance."""

    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs) -> Any:
        telemetry = get_telemetry()
        command_name = func.__name__
        player_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id) if interaction.guild_id else "dm"
        channel_id = (
            str(interaction.channel_id)
            if getattr(interaction, "channel_id", None) is not None
            else "dm"
        )
        start_time = time.time()
        success = False
        error_type = None

        try:
            result = await func(interaction, *args, **kwargs)
            success = True
            return result

        except Exception as e:
            error_type = type(e).__name__
            telemetry.track_error(
                error_type,
                command=command_name,
                player_id=player_id,
                error_details=str(e)
            )
            raise

        finally:
            # Track command usage
            duration_ms = (time.time() - start_time) * 1000
            telemetry.track_command(
                command_name,
                player_id,
                guild_id,
                success=success,
                duration_ms=duration_ms,
                channel_id=channel_id
            )

            # Track player activity if successful
            if success and hasattr(interaction, 'user'):
                bot = getattr(interaction, "client", None)
                service = getattr(bot, "state_service", None) if bot else None

                if service and hasattr(service, "player_status"):
                    try:
                        player_handle = str(interaction.user.display_name)
                        status = service.player_status(player_handle)
                        if status:
                            telemetry.track_player_activity(
                                player_id,
                                command_name,
                                status.get('reputation', 0),
                                status.get('influence', {})
                            )
                    except Exception:
                        pass  # Do not break command execution if telemetry fails

    return wrapper
