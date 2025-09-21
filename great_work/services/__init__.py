"""Application services layer scaffold.

This package will gradually absorb orchestration logic from legacy modules
such as ``great_work.service``. During the transition, we provide thin
re-exports to keep forward-compat imports working without changing behavior.
"""

# Re-export commonly used service types to aid progressive migration
try:  # pragma: no cover - simple import wiring
    from great_work.service import GameService as GameService  # type: ignore
except Exception:  # pragma: no cover - module may be in flux during refactors
    pass

