"""
JARVIS Master Controller - Unified entry point for ALL operations
"""
from __future__ import annotations
import asyncio
from typing import Dict, Any, List
from jarvis.core.multiagent_orchestrator import multiagent_orchestrator
from jarvis.core.universal_task_runner import universal_runner
from jarvis.workflows.hackathon_end_to_end import hackathon_pipeline
from jarvis.agents.assignment_agent import assignment_handler
from jarvis.agents.form_filler_agent import form_filler
from jarvis.browser.agent_browser import browser_orchestrator


class JarvisMasterController:
    async def do_everything(self, tasks: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        coros = []
        if tasks.get("moodle_assignments"):
            coros.append(("assignments", assignment_handler.process_assignment(subject=tasks.get("subject",""))))
        if tasks.get("find_jobs"):
            coros.append(("jobs", form_filler.scan_opportunities()))
        if tasks.get("find_hackathon"):
            coros.append(("hackathon", hackathon_pipeline.run_pipeline(auto_execute=True)))
        if tasks.get("parallel_intents"):
            coros.append(("parallel", universal_runner.run_all_parallel(tasks["parallel_intents"])))
        # Run all in parallel
        for name, coro in coros:
            try:
                results[name] = await coro
            except Exception as e:
                results[name] = {"error": str(e)}
        return results

    async def full_autonomous_run(self):
        tasks = {
            "moodle_assignments": True,
            "find_jobs": True,
            "find_hackathon": True,
            "parallel_intents": ["Research latest AI jobs", "Find hackathons this week", "Scan student ambassador programs"]
        }
        return await self.do_everything(tasks)


master_controller = JarvisMasterController()
