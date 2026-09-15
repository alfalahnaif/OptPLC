"""Validation must not block the event loop (P1-02, D-030).

A slow MATIEC compile used to run with subprocess.run on the event loop, stalling every other
request for up to 30 s. The repair loop now awaits ValidationAgent.validate_in_thread.
"""

import asyncio
import time

from app.agents import ValidationAgent
from app.database.database import AsyncSessionLocal
from app.database.repository import Repository
from app.services import repair_service
from app.services.repair_service import RepairService
from app.tests.test_repair_loop import save_plan_and_artifact

SLOW_COMPILE_SECONDS = 0.4


async def test_repair_loop_validation_runs_off_the_event_loop(monkeypatch) -> None:
    real_validate = ValidationAgent.validate

    class SlowValidationAgent(ValidationAgent):
        def validate(self, **kwargs):
            time.sleep(SLOW_COMPILE_SECONDS)  # stands in for a slow iec2c compile
            return real_validate(self, **kwargs)

    monkeypatch.setattr(repair_service, "ValidationAgent", SlowValidationAgent)

    stamps: list[float] = []

    async def ticker() -> None:
        for _ in range(10):
            await asyncio.sleep(0.05)
            stamps.append(time.perf_counter())

    async with AsyncSessionLocal() as db:
        await save_plan_and_artifact(db, Repository(), "Motor Control")
        report, _ = await asyncio.gather(RepairService(db).run_repair_loop("PRJ-0421"), ticker())

    assert report.finalStatus == "VERIFIED"
    gaps = [later - earlier for earlier, later in zip(stamps, stamps[1:])]
    # A blocked loop would leave one gap of about SLOW_COMPILE_SECONDS between ticks.
    assert max(gaps) < SLOW_COMPILE_SECONDS / 2
