"""Tone pack support for narrative prompts."""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml

_RANDOM = random.Random()  # nosec B311 - pseudo-RNG acceptable for tone sampling


def _random_choice(seq):
    return _RANDOM.choice(seq)


_TONE_PACK_PATH = Path(__file__).parent / "data" / "press_tone_packs.yaml"
_SETTING_ENV = "GREAT_WORK_PRESS_SETTING"


class ToneLibrary:
    """Loads tone packs and exposes seed snippets per event type."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _TONE_PACK_PATH
        self._packs: Dict[str, Dict[str, Dict[str, Union[str, List[str]]]]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._packs = {}
            return
        with self._path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        settings = raw.get("settings", {})
        self._packs = {
            str(setting): {
                str(event): {
                    key: self._normalise_value(value)
                    for key, value in (template or {}).items()
                    if value is not None
                }
                for event, template in (events or {}).items()
            }
            for setting, events in settings.items()
        }

    @staticmethod
    def _normalise_value(value: Union[str, List[str], None]) -> Union[str, List[str]]:
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if value is None:
            return ""
        return str(value)

    @property
    def available_settings(
        self,
    ) -> Dict[str, Dict[str, Dict[str, Union[str, List[str]]]]]:
        return self._packs

    def get_seed(
        self,
        event_type: str,
        setting: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Return tone seed for event/setting if defined."""

        chosen = setting or os.getenv(_SETTING_ENV, "post_cyberpunk_collapse")
        pack = self._packs.get(chosen)
        if not pack:
            return None
        seed = pack.get(event_type)
        if seed:
            return self._sample_seed(seed)
        # Fallback to default pack if the event is missing
        default_pack = self._packs.get("post_cyberpunk_collapse")
        if default_pack and default_pack.get(event_type):
            return self._sample_seed(default_pack[event_type])
        return None

    @staticmethod
    def _sample_seed(seed: Dict[str, Union[str, List[str]]]) -> Dict[str, str]:
        resolved: Dict[str, str] = {}
        for key, value in seed.items():
            if isinstance(value, list):
                choices = [item for item in value if item]
                if not choices:
                    continue
                resolved[key] = _random_choice(choices)
            else:
                if value:
                    resolved[key] = value
        return resolved


_TONE_LIBRARY: Optional[ToneLibrary] = None


def get_tone_seed(
    event_type: str, setting: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """Lookup helper for tone seeds."""

    global _TONE_LIBRARY
    if _TONE_LIBRARY is None:
        _TONE_LIBRARY = ToneLibrary()
    return _TONE_LIBRARY.get_seed(event_type, setting)


__all__ = ["ToneLibrary", "get_tone_seed"]
