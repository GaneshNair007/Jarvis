"""On-demand workforce adapter backed by real workflow components.

This module reports registered components separately from running processes.
It does not claim that catalog entries are autonomous workers or that code,
repositories, notifications, or submissions were made.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.workforce")


class AutonomousWorkforceSwarm:
    """Coordinates the implemented on-demand hackathon scout workflow."""

    COMPONENTS = (
        "scout",
        "analyst",
        "source_page_reader",
        "research_note_architect",
    )

    def __init__(self):
        self.task_history: List[Dict[str, Any]] = []

    def get_fleet_status(self) -> Dict[str, Any]:
        """Report implemented components without pretending they are worker processes."""
        return {
            "registered_components": len(self.COMPONENTS),
            "components": list(self.COMPONENTS),
            "active_workers": 0,
            "completed_worker_tasks": 0,
            "execution_mode": "on_demand_workflow",
            "status": "IDLE",
            "message": (
                "These are registered workflow components, not a 105-process agent fleet. "
                "Workers are not running between requests."
            ),
        }

    async def run_hackathon_opportunity_pipeline(
        self,
        target_phone: str = "+919324094474",
        location: str = "India",
        candidate_name: str = "Ganesh",
        output_workspace: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run live discovery and source-page research; never fake project creation or dispatch."""
        from jarvis.agents.hackathon_scout import hackathon_scout_swarm

        start_time = time.time()
        previous_workspace = hackathon_scout_swarm.architect.workspace_root
        if output_workspace is not None:
            hackathon_scout_swarm.architect.workspace_root = Path(output_workspace)

        try:
            scout_result = await hackathon_scout_swarm.execute_autonomous_scout_cycle(
                target_phone=target_phone,
                search_query=f"current hackathons {location} AI software students",
                send_notification=False,
            )
        finally:
            hackathon_scout_swarm.architect.workspace_root = previous_workspace

        found = scout_result.get("opportunities", [])
        summary = {
            "pipeline_id": f"workforce_{int(start_time * 1000)}",
            "status": scout_result.get("status", "unavailable"),
            "duration_sec": round(time.time() - start_time, 3),
            "candidate_name": candidate_name,
            "target_phone": target_phone,
            "hackathons_found": scout_result.get("total_discovered", 0),
            "pages_fetched": scout_result.get("pages_fetched", 0),
            "top_hackathon": found[0].get("title") if found else None,
            "research_note_paths": scout_result.get("research_notes", []),
            "page_failures": scout_result.get("page_failures", []),
            "notification": scout_result.get(
                "notification",
                {"status": "not_requested", "message": "No external notification was sent."},
            ),
            "next_steps": scout_result.get("next_steps", []),
            "fleet_status": self.get_fleet_status(),
        }
        self.task_history.append(summary)
        logger.info(
            "Hackathon workflow finished with status=%s, discovered=%s, pages_fetched=%s",
            summary["status"],
            summary["hackathons_found"],
            summary["pages_fetched"],
        )
        return summary


autonomous_workforce = AutonomousWorkforceSwarm()
