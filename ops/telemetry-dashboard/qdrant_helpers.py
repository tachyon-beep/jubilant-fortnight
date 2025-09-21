"""Helpers for optional Qdrant-backed semantic search in the dashboard."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional

ENABLE_QDRANT_SEARCH = os.getenv("ENABLE_QDRANT_SEARCH", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_QDRANT_IMPORT_ERROR: Optional[str] = None
try:  # pragma: no cover - heavy dependency validated at runtime when enabled
    from great_work.tools.qdrant_manager import QdrantManager, DEFAULT_MODEL
except Exception as exc:  # pragma: no cover - keep module importable without deps
    QdrantManager = None  # type: ignore[assignment]
    DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    _QDRANT_IMPORT_ERROR = str(exc)

LOGGER = logging.getLogger(__name__)

_QDRANT_URL_DEFAULT = os.getenv("QDRANT_URL", "http://localhost:6333")
_QDRANT_COLLECTION_DEFAULT = os.getenv("QDRANT_COLLECTION", "great-work-knowledge")
_QDRANT_MODEL_DEFAULT = os.getenv("QDRANT_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=1)
def _cached_manager() -> Optional[QdrantManager]:  # pragma: no cover - thin wrapper
    """Initialise and cache a Qdrant manager instance."""
    if not ENABLE_QDRANT_SEARCH:
        return None
    if QdrantManager is None:
        raise RuntimeError(_QDRANT_IMPORT_ERROR or "Qdrant dependencies are unavailable")
    return QdrantManager(
        url=_QDRANT_URL_DEFAULT,
        collection=_QDRANT_COLLECTION_DEFAULT,
        model_name=_QDRANT_MODEL_DEFAULT,
    )


def get_status() -> tuple[bool, Optional[str]]:
    """Return whether semantic search is available and an optional status message."""
    if not ENABLE_QDRANT_SEARCH:
        return False, None
    try:
        manager = _cached_manager()
    except Exception as exc:  # pragma: no cover - surfaced to caller
        LOGGER.warning("Qdrant manager initialisation failed: %s", exc)
        return False, str(exc)
    if manager is None:
        return False, "Semantic search disabled"
    return True, None


def search_press(query: str, limit: int = 5) -> List[Dict[str, object]]:
    """Perform semantic search against indexed press releases."""
    if not ENABLE_QDRANT_SEARCH:
        raise RuntimeError("Semantic search disabled")
    if not query.strip():
        raise ValueError("query must not be empty")
    try:
        manager = _cached_manager()
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    if manager is None:
        raise RuntimeError("Qdrant manager unavailable")

    results = manager.search(query, limit=limit)
    simplified: List[Dict[str, object]] = []
    for result in results:
        payload = result.get("payload") or {}
        metadata = payload.get("metadata") or {}
        content = str(payload.get("content") or "").strip()
        excerpt = " ".join(content.split())
        if len(excerpt) > 280:
            excerpt = excerpt[:277].rstrip() + "..."
        simplified.append(
            {
                "id": payload.get("id") or result.get("id"),
                "headline": payload.get("title") or payload.get("headline") or "Untitled",
                "excerpt": excerpt,
                "score": result.get("score"),
                "timestamp": metadata.get("timestamp"),
                "metadata": metadata,
            }
        )
    return simplified
