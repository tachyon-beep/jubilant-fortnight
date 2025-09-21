"""Discord adapter scaffold.

Thin re-exports to ease migration of Discord-facing code.
"""

from __future__ import annotations

try:  # pragma: no cover - trivial wiring
    from great_work.discord_bot import ChannelRouter as ChannelRouter  # re-export
except Exception:  # pragma: no cover
    pass

