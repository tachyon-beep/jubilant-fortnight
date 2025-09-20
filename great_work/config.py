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
    timeline_start_year: int
    gazette_times: list[str]
    symposium_day: str
    symposium_first_reminder_hours: float
    symposium_escalation_hours: float
    symposium_max_backlog: int
    symposium_max_per_player: int
    symposium_proposal_expiry_days: int
    symposium_pledge_base: int
    symposium_pledge_escalation_cap: int
    symposium_grace_window_days: int
    symposium_grace_misses: int
    symposium_recent_window: int
    symposium_scoring_max_age_days: int
    symposium_scoring_age_weight: float
    symposium_scoring_fresh_bonus: float
    symposium_scoring_repeat_penalty: float
    symposium_debt_reprisal_threshold: int
    symposium_debt_reprisal_penalty: int
    symposium_debt_reprisal_cooldown_days: int
    confidence_wagers: Dict[str, Dict[str, int]]
    reputation_bounds: Dict[str, int]
    action_thresholds: Dict[str, int]
    influence_caps: Dict[str, float]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Settings":
        reputation = dict(data["reputation"])
        thresholds = reputation.get("thresholds", {})
        influence_caps = data.get("influence_caps", {"base": 5, "per_reputation": 0.0})
        symposium_cfg = data.get("symposium", {})
        reminder_cfg = symposium_cfg.get("reminder_hours", {})
        proposal_expiry_days = int(symposium_cfg.get("proposal_expiry_days", 21))
        max_backlog = int(symposium_cfg.get("proposal_backlog", 10))
        max_per_player = int(symposium_cfg.get("max_per_player", 3))
        pledge_cfg = symposium_cfg.get("pledge", {})
        pledge_base = int(pledge_cfg.get("base_influence", 2))
        pledge_cap = int(pledge_cfg.get("escalation_cap", 5))
        grace_cfg = symposium_cfg.get("grace", {})
        grace_window_days = int(grace_cfg.get("window_days", 28))
        grace_misses = int(grace_cfg.get("misses", 1))
        scoring_cfg = symposium_cfg.get("scoring", {})
        recent_window = int(scoring_cfg.get("recent_window", 4))
        max_age_days = int(scoring_cfg.get("max_age_days", 28))
        age_weight = float(scoring_cfg.get("age_weight", 1.0))
        fresh_bonus = float(scoring_cfg.get("fresh_bonus", 0.5))
        repeat_penalty = float(scoring_cfg.get("repeat_penalty", 0.75))
        debt_cfg = symposium_cfg.get("debt", {})
        reprisal_threshold = int(debt_cfg.get("reprisal_threshold", 6))
        reprisal_penalty = int(debt_cfg.get("reprisal_penalty", 2))
        reprisal_cooldown = int(debt_cfg.get("reprisal_cooldown_days", 7))
        return Settings(
            time_scale_days_per_year=data["time_scale"]["real_days_per_year"],
            timeline_start_year=int(data["time_scale"].get("start_year", 1920)),
            gazette_times=list(data["timing"]["gazette_times"]),
            symposium_day=data["timing"]["symposium_day"],
            symposium_first_reminder_hours=float(reminder_cfg.get("first", 12.0)),
            symposium_escalation_hours=float(reminder_cfg.get("escalation", 24.0)),
            symposium_max_backlog=max_backlog,
            symposium_max_per_player=max_per_player,
            symposium_proposal_expiry_days=proposal_expiry_days,
            symposium_pledge_base=pledge_base,
            symposium_pledge_escalation_cap=pledge_cap,
            symposium_grace_window_days=grace_window_days,
            symposium_grace_misses=grace_misses,
            symposium_recent_window=recent_window,
            symposium_scoring_max_age_days=max_age_days,
            symposium_scoring_age_weight=age_weight,
            symposium_scoring_fresh_bonus=fresh_bonus,
            symposium_scoring_repeat_penalty=repeat_penalty,
            symposium_debt_reprisal_threshold=reprisal_threshold,
            symposium_debt_reprisal_penalty=reprisal_penalty,
            symposium_debt_reprisal_cooldown_days=reprisal_cooldown,
            confidence_wagers=data["confidence_wagers"],
            reputation_bounds=reputation,
            action_thresholds={k: int(v) for k, v in thresholds.items()},
            influence_caps={"base": float(influence_caps.get("base", 5)), "per_reputation": float(influence_caps.get("per_reputation", 0.0))},
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
