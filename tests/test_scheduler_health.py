"""Scheduler health integration tests."""
from __future__ import annotations

from pathlib import Path

from great_work import scheduler as scheduler_module
from great_work.service import GameService


def test_gazette_scheduler_registers_jobs(tmp_path):
    instances = []

    class FakeScheduler:
        def __init__(self):
            self.jobs = []
            self.started = False
            instances.append(self)

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append((trigger, kwargs))

        def start(self):
            self.started = True

    original_scheduler = scheduler_module.BackgroundScheduler
    scheduler_module.BackgroundScheduler = FakeScheduler
    try:
        service = GameService(tmp_path / "state.db")
        gs = scheduler_module.GazetteScheduler(service)
        gs.start()
    finally:
        scheduler_module.BackgroundScheduler = original_scheduler

    assert instances, "scheduler was not constructed"
    fake = instances[0]
    digest_jobs = [kwargs for trigger, kwargs in fake.jobs if trigger == "cron" and "hour" in kwargs]
    assert digest_jobs, "expected digest cron jobs"
    assert fake.started is True
