"""
JARVIS Full Autonomy Service
Runs all tasks in parallel continuously
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from jarvis.core.master_controller import master_controller
from jarvis.core.logger import get_logger

logger = get_logger("services.autonomy")


class FullAutonomyService:
    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("Full autonomy service started")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()

    async def _loop(self):
        while self.running:
            try:
                await master_controller.full_autonomous_run()
                await asyncio.sleep(300)  # Run every 5 min
            except Exception as e:
                logger.error(f"Autonomy loop error: {e}")
                await asyncio.sleep(60)


full_autonomy = FullAutonomyService()
