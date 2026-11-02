"""
JARVIS Task Reflection Layer (Post-Goal Retrospective & Continuous Improvement)
Analyzes completed or terminated task graphs to extract successes, failures,
architectural improvements, and new opportunities, persisting reflections for permanent learning.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskStatus
from jarvis.core.logger import get_logger

logger = get_logger("core.task_reflection")


class ReflectionRecord(BaseModel):
    goal_id: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    successes: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class TaskReflectionEngine:
    """
    Evaluates goal execution outcomes and synthesizes deep reflective insights
    to continuously improve future DAG generation and agent dispatching.
    """

    def __init__(self, storage_path: str = "data/reflections.json"):
        self.storage_path = Path(storage_path)
        self.reflections: Dict[str, ReflectionRecord] = {}
        self._load_storage()

    def _load_storage(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for gid, rec in data.items():
                    self.reflections[gid] = ReflectionRecord(**rec)
            except Exception as e:
                logger.warning(f"Could not load reflections from {self.storage_path}: {e}")

    def _save_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = {gid: r.model_dump() for gid, r in self.reflections.items()}
            self.storage_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to persist reflections to {self.storage_path}: {e}")

    def reflect_on_goal(self, graph: TaskGraph) -> ReflectionRecord:
        """Analyzes a finished TaskGraph and generates a permanent ReflectionRecord."""
        successes = []
        failures = []
        improvements = []
        opportunities = []

        total_tasks = len(graph.nodes)
        completed_tasks = 0
        failed_tasks = 0
        retried_tasks = 0

        for task_id, node in graph.nodes.items():
            if node.status == TaskStatus.COMPLETED:
                completed_tasks += 1
                successes.append(f"Task '{node.name}' ({task_id}) completed cleanly by [{node.assigned_agent}].")
                # Look for opportunities in task outputs
                for k, v in node.outputs.items():
                    if "opportunity" in k.lower() or "suggest" in k.lower() or "idea" in k.lower():
                        opportunities.append(f"Opportunity from {node.name}: {v}")
            elif node.status == TaskStatus.FAILED:
                failed_tasks += 1
                err = node.metadata.get("last_error", "Unknown error")
                failures.append(f"Task '{node.name}' ({task_id}) FAILED after {node.retry_count} retries: {err}")
                improvements.append(f"Harden tool execution and timeout limits for [{node.department}] tasks.")

            if node.retry_count > 0:
                retried_tasks += 1

        if retried_tasks > 0 and failed_tasks == 0:
            improvements.append(f"{retried_tasks} task(s) required retries before succeeding; refine initial prompt templates.")

        if completed_tasks == total_tasks and total_tasks > 0:
            successes.append(f"Goal '{graph.goal_id}' achieved 100% completion across all {total_tasks} DAG nodes.")
            opportunities.append(f"Synthesize deliverables from goal '{graph.goal_id}' into reusable skill catalog.")

        metrics = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "retried_tasks": retried_tasks,
            "completion_rate": round((completed_tasks / max(total_tasks, 1)) * 100, 1),
        }

        record = ReflectionRecord(
            goal_id=graph.goal_id,
            successes=successes,
            failures=failures,
            improvements=improvements,
            opportunities=opportunities,
            metrics=metrics,
        )

        self.reflections[graph.goal_id] = record
        self._save_storage()
        logger.info(f"TaskReflectionEngine: Generated reflection for goal '{graph.goal_id}' (Completion={metrics['completion_rate']}%)")
        return record

    def get_reflection(self, goal_id: str) -> Optional[ReflectionRecord]:
        return self.reflections.get(goal_id)

    def list_reflections(self) -> List[Dict[str, Any]]:
        return [r.model_dump() for r in self.reflections.values()]


# Global Singleton Instance
task_reflection = TaskReflectionEngine()
