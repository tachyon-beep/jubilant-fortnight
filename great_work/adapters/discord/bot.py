"""Discord bot adapter and routing helpers.

This module holds the canonical `ChannelRouter` used to configure Discord
channels via environment variables. The legacy `great_work.discord_bot`
imports this symbol to preserve backward compatibility.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

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
