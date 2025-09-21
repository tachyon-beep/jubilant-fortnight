"""Game service facade.

Provides a stable import path for the main game orchestration service while we
incrementally migrate logic out of ``great_work.service`` into smaller modules.
"""

from __future__ import annotations

try:  # pragma: no cover - trivial aliasing
    from great_work.service import GameService as GameService  # re-export
except Exception:  # pragma: no cover
    # During early scaffolding, tolerate missing legacy module in some contexts.
    GameService = object  # type: ignore

