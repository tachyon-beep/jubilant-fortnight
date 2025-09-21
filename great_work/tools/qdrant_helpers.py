"""Shared helpers for optional Qdrant-powered semantic search."""

from __future__ import annotations

import textwrap
from functools import lru_cache
from typing import Any, Dict, List

try:  # pragma: no cover - import guarded for optional dependency
    from .qdrant_manager import QdrantManager
except Exception as exc:  # pragma: no cover - captured for runtime error message
    QdrantManager = None  # type: ignore[assignment]
    _IMPORT_ERROR: Exception | None = exc
else:
    _IMPORT_ERROR = None


@lru_cache(maxsize=1)
def _get_manager() -> "QdrantManager":  # pragma: no cover - thin wrapper
    if QdrantManager is None:
        raise RuntimeError(
            "Qdrant support is unavailable (missing dependencies)."
            f" Details: {_IMPORT_ERROR}"
        )
    return QdrantManager()


def fetch_related_press_snippets(query: str, limit: int = 3) -> List[str]:
    """Return formatted semantic matches from Qdrant for the given query."""

    manager = _get_manager()
    try:
        results = manager.search(query, limit=limit)
    except Exception as exc:  # pragma: no cover - network failure, etc.
        raise RuntimeError(f"Qdrant search failed: {exc}") from exc

    snippets: List[str] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        payload: Dict[str, Any] = result.get("payload") or {}
        if not isinstance(payload, dict):
            continue

        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").strip()
        metadata = payload.get("metadata")
        timestamp = metadata.get("timestamp") if isinstance(metadata, dict) else None

        snippet_source = content.replace("\n", " ") if content else ""
        body = (
            textwrap.shorten(snippet_source, width=180, placeholder="…")
            if snippet_source
            else ""
        )

        header_parts = [title] if title else []
        if timestamp:
            header_parts.append(f"({timestamp})")
        header = " ".join(part for part in header_parts if part).strip()

        if header and body:
            summary = f"{header}: {body}"
        elif header:
            summary = header
        elif body:
            summary = body
        else:
            continue

        snippets.append(summary)
        if len(snippets) >= limit:
            break

    return snippets
