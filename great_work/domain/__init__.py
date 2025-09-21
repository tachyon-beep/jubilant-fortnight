"""Domain layer scaffold.

Pure domain types and policies will move here. For now, we keep the legacy
``great_work.models`` as the source of truth.
"""

try:  # pragma: no cover - optional convenience re-exports
    from great_work import models as models  # re-export module for ergonomic imports
except Exception:  # pragma: no cover
    pass

