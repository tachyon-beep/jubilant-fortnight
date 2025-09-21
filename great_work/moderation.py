"""Moderation utilities for player-facing and generated content."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class ModerationDecision:
    """Result of evaluating a piece of content."""

    allowed: bool
    severity: str = "allow"  # allow, warn, block
    reason: Optional[str] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] | None = None
    raw: Any | None = None
    text_hash: Optional[str] = None


class GuardianModerator:
    """Wraps Granite Guardian moderation with lightweight prefilters."""

    _DEFAULT_BLOCKLIST = {
        "kill",
        "murder",
        "suicide",
        "terrorist",
        "bomb",
        "rape",
    }

    _DEFAULT_SUSPECT_PATTERNS = {
        "hate speech",
        "slur",
        "graphic violence",
        "sexual violence",
        "self harm",
    }

    _DEFAULT_CATEGORIES = [
        "Hate",
        "Abuse",
        "Profanity",
        "Sexual",
        "Violence",
        "Self-Harm",
        "Illicit",
    ]

    def __init__(self) -> None:
        self._mode = os.getenv("GREAT_WORK_GUARDIAN_MODE", "sidecar").strip().lower() or "sidecar"
        self._enabled = os.getenv("GREAT_WORK_GUARDIAN_ENABLED", "false").lower() in {
            "true",
            "1",
            "on",
            "yes",
        }
        self._endpoint = os.getenv(
            "GREAT_WORK_GUARDIAN_URL",
            "http://localhost:8088/moderate",
        ).strip()
        self._timeout = float(os.getenv("GREAT_WORK_GUARDIAN_TIMEOUT", "5.0") or 5.0)
        self._api_key = os.getenv("GREAT_WORK_GUARDIAN_API_KEY")
        categories_env = os.getenv("GREAT_WORK_GUARDIAN_CATEGORIES")
        if categories_env:
            categories = [item.strip() for item in categories_env.split(",") if item.strip()]
            self._categories = categories or self._DEFAULT_CATEGORIES
        else:
            self._categories = self._DEFAULT_CATEGORIES
        self._always_call_guardian = (
            os.getenv("GREAT_WORK_GUARDIAN_ALWAYS", "false").lower() in {"true", "1", "on"}
        )
        self._blocklist = {term.lower() for term in self._DEFAULT_BLOCKLIST}
        self._suspect_patterns = {term.lower() for term in self._DEFAULT_SUSPECT_PATTERNS}
        self._allowlist: Dict[str, Dict[str, Any]] = {}

        self._local_model_path: Optional[Path] = None
        self._local_pipeline = None
        self._local_max_tokens = int(os.getenv("GREAT_WORK_GUARDIAN_LOCAL_TOKENS", "2") or 2)
        if self._mode == "local":
            local_path = os.getenv("GREAT_WORK_GUARDIAN_LOCAL_PATH")
            if local_path:
                self._local_model_path = Path(local_path)
                self._enabled = True
            else:
                logger.warning(
                    "Guardian local mode requested but GREAT_WORK_GUARDIAN_LOCAL_PATH is not set"
                )
                self._enabled = False
        else:
            if not self._endpoint:
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def load_allowlist(self, entries: Iterable[Dict[str, Any]]) -> None:
        self._allowlist = {}
        for entry in entries:
            text_hash = entry.get("text_hash")
            if not text_hash:
                continue
            self._allowlist[text_hash] = dict(entry)

    def add_allowlist_entry(self, entry: Dict[str, Any]) -> None:
        text_hash = entry.get("text_hash")
        if not text_hash:
            return
        self._allowlist[text_hash] = dict(entry)

    def remove_allowlist_entry(self, text_hash: str) -> None:
        self._allowlist.pop(text_hash, None)

    def _is_allowlisted(
        self,
        *,
        text_hash: str,
        surface: str,
        stage: str,
        category: Optional[str],
        now: Optional[datetime] = None,
    ) -> bool:
        entry = self._allowlist.get(text_hash)
        if not entry:
            return False
        expires_at = entry.get("expires_at")
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
            except ValueError:
                expires_dt = None
            if expires_dt is not None:
                current = now or datetime.now(timezone.utc)
                if expires_dt < current:
                    return False
        stage_override = entry.get("stage")
        if stage_override and stage_override != stage:
            return False
        surface_override = entry.get("surface")
        if surface_override and surface_override != surface:
            return False
        category_override = entry.get("category")
        if category_override and category and category_override != category:
            return False
        return True

    def review(
        self,
        text: str,
        *,
        surface: str,
        actor: Optional[str],
        stage: str,
    ) -> ModerationDecision:
        """Assess ``text`` and determine if it is allowed."""

        cleaned = text.strip()
        if not cleaned:
            return ModerationDecision(True, metadata={"suspect": False}, text_hash=self.compute_hash(""))

        text_hash = self.compute_hash(cleaned)
        now = datetime.now(timezone.utc)
        if self._is_allowlisted(
            text_hash=text_hash,
            surface=surface,
            stage=stage,
            category=None,
            now=now,
        ):
            metadata = {
                "surface": surface,
                "actor": actor,
                "stage": stage,
                "source": "allowlist",
                "text_hash": text_hash,
            }
            return ModerationDecision(True, severity="allow", metadata=metadata, text_hash=text_hash)

        prefilter_decision = self._prefilter(cleaned)
        if not prefilter_decision.allowed:
            prefilter_decision.metadata = prefilter_decision.metadata or {}
            prefilter_decision.metadata.update(
                {
                    "surface": surface,
                    "actor": actor,
                    "stage": stage,
                    "source": "prefilter",
                    "text_hash": text_hash,
                }
            )
            prefilter_decision.text_hash = text_hash
            return prefilter_decision

        should_call_guardian = self._always_call_guardian or prefilter_decision.metadata.get(
            "suspect", False
        )

        if not self.enabled:
            return ModerationDecision(True, metadata={"suspect": prefilter_decision.metadata.get("suspect", False), "text_hash": text_hash}, text_hash=text_hash)

        if not should_call_guardian:
            return ModerationDecision(True, metadata={"suspect": False, "text_hash": text_hash}, text_hash=text_hash)

        if self._mode == "local":
            response = self._score_local(cleaned)
        else:
            response = self._call_guardian(cleaned, surface=surface, actor=actor, stage=stage)
        if response is None:
            return ModerationDecision(True, metadata={"suspect": True, "text_hash": text_hash}, text_hash=text_hash)

        violations = [entry for entry in response if entry.get("label", "").lower().startswith("y")]
        if not violations:
            metadata = {
                "surface": surface,
                "actor": actor,
                "stage": stage,
                "source": "guardian" if self._mode != "local" else "guardian_local",
                "violations": violations,
                "text_hash": text_hash,
            }
            return ModerationDecision(True, severity="allow", metadata=metadata, raw=response, text_hash=text_hash)

        top = violations[0]
        reason = top.get("category", "guardian_flagged")
        if self._is_allowlisted(
            text_hash=text_hash,
            surface=surface,
            stage=stage,
            category=reason,
            now=now,
        ):
            metadata = {
                "surface": surface,
                "actor": actor,
                "stage": stage,
                "source": "allowlist",
                "text_hash": text_hash,
                "overridden_category": reason,
            }
            return ModerationDecision(True, severity="allow", metadata=metadata, raw=response, text_hash=text_hash)

        metadata = {
            "surface": surface,
            "actor": actor,
            "stage": stage,
            "source": "guardian" if self._mode != "local" else "guardian_local",
            "violations": violations,
            "text_hash": text_hash,
        }
        return ModerationDecision(
            allowed=False,
            severity="block",
            reason=f"Guardian flagged category {reason}",
            category=reason,
            metadata=metadata,
            raw=response,
            text_hash=text_hash,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefilter(self, text: str) -> ModerationDecision:
        lowered = text.lower()
        for term in self._blocklist:
            if term in lowered:
                return ModerationDecision(
                    allowed=False,
                    severity="block",
                    reason=f"Contains blocked term '{term}'",
                    category="blocklist",
                    metadata={"term": term},
                )
        suspect_hits = [term for term in self._suspect_patterns if term in lowered]
        if suspect_hits:
            return ModerationDecision(
                allowed=True,
                severity="warn",
                metadata={"suspect": True, "terms": suspect_hits},
            )
        return ModerationDecision(True, metadata={"suspect": False})

    def _call_guardian(
        self,
        text: str,
        *,
        surface: str,
        actor: Optional[str],
        stage: str,
    ) -> Optional[List[Dict[str, Any]]]:
        payload = {
            "input": text,
            "categories": self._categories,
            "metadata": {
                "surface": surface,
                "actor": actor,
                "stage": stage,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self._endpoint, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read().decode("utf-8")
                document = json.loads(body)
        except urllib.error.URLError:
            logger.exception("Guardian sidecar request failed")
            return None
        except json.JSONDecodeError:
            logger.exception("Guardian sidecar returned invalid JSON")
            return None

        results = document.get("results") or document.get("scores") or document.get("categories")
        if isinstance(results, list):
            return results
        if isinstance(results, dict):
            return [{"category": key, "label": value} for key, value in results.items()]
        logger.debug("Guardian response did not include recognised structure: %s", document)
        return None

    def _ensure_local_pipeline(self):  # pragma: no cover - heavy dependency
        if self._local_pipeline is not None:
            return self._local_pipeline
        if self._local_model_path is None:
            raise RuntimeError("Local Guardian mode requested without GREAT_WORK_GUARDIAN_LOCAL_PATH")
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, TextGenerationPipeline
        except ImportError as exc:  # pragma: no cover - instructions only
            raise RuntimeError(
                "transformers must be installed to run Guardian locally. Install with 'pip install transformers accelerate'."
            ) from exc
        logger.info("Loading Guardian model from %s", self._local_model_path)
        tokenizer = AutoTokenizer.from_pretrained(self._local_model_path)
        model = AutoModelForCausalLM.from_pretrained(self._local_model_path)
        pipeline = TextGenerationPipeline(model=model, tokenizer=tokenizer, device_map="auto")
        self._local_pipeline = pipeline
        return pipeline

    def _build_prompt(self, category: str, text: str) -> str:
        system = (
            "You are Granite Guardian, a safety classifier. Determine whether the user text violates the "
            "{category} policy or guidelines. Reply strictly with 'Yes' if it violates the policy or 'No' "
            "if it is acceptable."
        ).format(category=category)
        return (
            f"<s>[INST] <<SYS>>\n{system}\n<</SYS>>\nUser text:\n{text}\n[/INST]"
        )

    def _score_local(self, text: str) -> Optional[List[Dict[str, Any]]]:  # pragma: no cover - heavy path
        try:
            pipeline = self._ensure_local_pipeline()
        except Exception:
            logger.exception("Failed to load local Guardian pipeline")
            return None

        results: List[Dict[str, Any]] = []
        for category in self._categories:
            prompt = self._build_prompt(category, text)
            generations = pipeline(
                prompt,
                max_new_tokens=self._local_max_tokens,
                do_sample=False,
                temperature=0.0,
                return_full_text=False,
            )
            answer = generations[0]["generated_text"].strip()
            label = "Yes" if answer.lower().startswith("yes") else "No"
            results.append(
                {
                    "category": category,
                    "label": label,
                    "answer": answer,
                }
            )
        return results


__all__ = ["GuardianModerator", "ModerationDecision"]
