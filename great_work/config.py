"""Configuration loading utilities for The Great Work."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_SETTINGS_PATH = Path(__file__).parent / "data" / "settings.yaml"


@dataclass(frozen=True)
class Settings:
    """Typed view over the settings YAML file."""

    time_scale_days_per_year: int
    gazette_times: list[str]
    symposium_day: str
    confidence_wagers: Dict[str, Dict[str, int]]
    reputation_bounds: Dict[str, int]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Settings":
        return Settings(
            time_scale_days_per_year=data["time_scale"]["real_days_per_year"],
            gazette_times=list(data["timing"]["gazette_times"]),
            symposium_day=data["timing"]["symposium_day"],
            confidence_wagers=data["confidence_wagers"],
            reputation_bounds=data["reputation"],
        )


class SettingsLoader:
    """Loads and caches settings from YAML configuration files."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_SETTINGS_PATH
        self._cache: Settings | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self, force: bool = False) -> Settings:
        if self._cache is not None and not force:
            return self._cache
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        self._cache = Settings.from_dict(data)
        return self._cache


def get_settings() -> Settings:
    """Convenience accessor for default settings."""

    return SettingsLoader().load()


__all__ = ["Settings", "SettingsLoader", "get_settings"]
