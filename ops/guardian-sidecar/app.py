"""FastAPI wrapper that exposes Granite Guardian moderation as an HTTP sidecar."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Ensure Guardian runs in local mode
os.environ.setdefault("GREAT_WORK_GUARDIAN_MODE", "local")
local_path = os.environ.get("GRANITE_MODEL_PATH") or os.environ.get("GREAT_WORK_GUARDIAN_LOCAL_PATH")
if local_path:
    os.environ.setdefault("GREAT_WORK_GUARDIAN_LOCAL_PATH", local_path)
else:
    os.environ.setdefault("GREAT_WORK_GUARDIAN_LOCAL_PATH", "/app/models/guardian")

from great_work.moderation import GuardianModerator

LOGGER = logging.getLogger("guardian-sidecar")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Granite Guardian Sidecar", version="1.0.0")
moderator = GuardianModerator()


class ScoreRequest(BaseModel):
    input: str
    categories: Optional[List[str]] = None
    metadata: Optional[dict] = None


class ScoreResponse(BaseModel):
    results: List[dict]


@app.get("/health")
def health() -> dict:
    path = moderator._local_model_path  # type: ignore[attr-defined]
    ready = path is not None and Path(path).exists()
    return {"status": "ok" if ready else "missing_model", "model_path": str(path)}


@app.post("/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    text = request.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="input must not be empty")

    categories = request.categories or list(moderator._categories)  # type: ignore[attr-defined]
    original_categories = list(moderator._categories)  # type: ignore[attr-defined]
    try:
        moderator._categories = categories  # type: ignore[attr-defined]
        results = moderator._score_local(text)
    except Exception as exc:  # pragma: no cover - heavy path
        LOGGER.exception("Guardian local scoring failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        moderator._categories = original_categories  # type: ignore[attr-defined]

    if results is None:
        raise HTTPException(status_code=503, detail="Guardian scoring unavailable")

    payload = []
    for item in results:
        record = dict(item)
        record.setdefault("category", categories[len(payload)] if len(categories) > len(payload) else None)
        payload.append(record)

    return ScoreResponse(results=payload)
