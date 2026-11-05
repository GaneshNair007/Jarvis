"""
JARVIS Reflection Engine - Execution Analyzer
Analyzes task outcomes, failure logs, execution durations, and completion rates.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskStatus


class ExecutionAnalysis(BaseModel):
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    retried_tasks: int
    completion_rate_pct: float
    bottlenecks: List[str] = Field(default_factory=list)
    repeated_failures: Dict[str, int] = Field(default_factory=dict)
    average_duration: float = 0.0


class ExecutionAnalyzer:
    """Analyzes runtime telemetry and execution logs of task graphs."""

    def analyze_graph(self, graph: TaskGraph) -> ExecutionAnalysis:
        total = len(graph.nodes)
        completed = 0
        failed = 0
        retried = 0
        bottlenecks = []
        repeated_failures: Dict[str, int] = {}

        for task_id, node in graph.nodes.items():
            if node.status == TaskStatus.COMPLETED:
                completed += 1
            elif node.status == TaskStatus.FAILED:
                failed += 1
                err = node.metadata.get("last_error", "Unknown error")
                repeated_failures[err] = repeated_failures.get(err, 0) + 1

            if node.retry_count > 0:
                retried += 1
                if node.retry_count >= 2:
                    bottlenecks.append(f"Task '{node.name}' ({task_id}) required {node.retry_count} retries.")

        rate = round((completed / max(total, 1)) * 100.0, 1)

        return ExecutionAnalysis(
            total_tasks=total,
            completed_tasks=completed,
            failed_tasks=failed,
            retried_tasks=retried,
            completion_rate_pct=rate,
            bottlenecks=bottlenecks,
            repeated_failures=repeated_failures,
        )
