"""Scheduler utilities for Gazette ticks.

Compatibility module that forwards to the infrastructure implementation.
"""

from __future__ import annotations

from .infrastructure.scheduler import GazetteScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from .telemetry import get_telemetry

__all__ = ["GazetteScheduler", "BackgroundScheduler", "get_telemetry"]
