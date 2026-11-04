"""
JARVIS Universal Task Runner - Runs everything in parallel
"""
from __future__ import annotations
import asyncio
from typing import List, Dict, Any
from jarvis.core.multiagent_orchestrator import multiagent_orchestrator
from jarvis.core.task_executor import TaskExecutor


class UniversalTaskRunner:
    def __init__(self):
        self.running = False

    async def run_all_parallel(self, intents: List[str]) -> Dict[str, Any]:
        self.running = True
        goals = []
        for intent in intents:
            goal = await multiagent_orchestrator.create_goal_from_intent(intent)
            goals.append(goal)
        # Execute all in parallel
        coros = []
        for goal in goals:
            graph = await multiagent_orchestrator.decompose_to_dag(goal, goal.description)
            executor = TaskExecutor()
            coros.append(executor.run(graph))
        results = await asyncio.gather(*coros, return_exceptions=True)
        self.running = False
        return {"count": len(results), "status": "completed"}


universal_runner = UniversalTaskRunner()
