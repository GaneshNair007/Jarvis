"""
JARVIS Task Scheduler (Priority Queue & Concurrency Controller)
Manages the DAG task state machine, priority-based dispatching,
concurrency limits, and downstream dependency unblocking.
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus, Priority
from jarvis.core.logger import get_logger

logger = get_logger("core.task_scheduler")

# Numeric priority for min-heap/sorting (lower number = higher priority)
PRIORITY_WEIGHTS = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
}


class TaskScheduler:
    """
    State machine and concurrency manager for executing TaskGraph nodes.
    Maintains active task queues, dispatches ready tasks according to Priority,
    and enforces maximum concurrent running task constraints.
    """

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.running_tasks: Set[str] = set()

    def get_dispatchable_tasks(self, graph: TaskGraph) -> List[TaskNode]:
        """
        Returns the next batch of tasks ready to execute, respecting
        dependencies, priority order, and max concurrency limit.
        """
        available_slots = max(0, self.max_concurrency - len(self.running_tasks))
        if available_slots == 0:
            return []

        # Query DAG for all ready tasks
        ready_candidates = graph.get_ready_tasks()

        # Exclude currently running tasks
        candidates = [t for t in ready_candidates if t.task_id not in self.running_tasks]

        # Sort by priority (CRITICAL first, then HIGH, MEDIUM, LOW)
        candidates.sort(key=lambda t: PRIORITY_WEIGHTS.get(t.priority, 2))

        # Take up to available concurrency slots
        dispatch_batch = candidates[:available_slots]
        return dispatch_batch

    def mark_started(self, graph: TaskGraph, task_id: str, agent_id: Optional[str] = None) -> Optional[TaskNode]:
        """Transitions a task into RUNNING state and registers it in active running set."""
        node = graph.nodes.get(task_id)
        if not node:
            logger.error(f"Task '{task_id}' not found in graph.")
            return None

        node.mark_running(agent_id=agent_id)
        self.running_tasks.add(task_id)
        logger.info(f"Task '{task_id}' ({node.name}) marked RUNNING with agent [{node.assigned_agent}]. Active running: {len(self.running_tasks)}")
        return node

    def mark_completed(self, graph: TaskGraph, task_id: str, outputs: Optional[Dict[str, Any]] = None) -> Optional[TaskNode]:
        """
        Transitions a task to COMPLETED, unblocks downstream dependent tasks,
        and releases concurrency slot.
        """
        node = graph.nodes.get(task_id)
        if not node:
            logger.error(f"Task '{task_id}' not found in graph.")
            return None

        node.mark_completed(outputs=outputs)
        self.running_tasks.discard(task_id)
        logger.info(f"Task '{task_id}' ({node.name}) COMPLETED. Active running: {len(self.running_tasks)}")

        # Check downstream dependent nodes
        downstream = graph.edges.get(task_id, [])
        for child_id in downstream:
            child_node = graph.nodes.get(child_id)
            if child_node and child_node.status in (TaskStatus.PENDING, TaskStatus.BLOCKED):
                # Verify if all dependencies of child are now completed
                all_deps_done = all(
                    graph.nodes.get(dep) and graph.nodes[dep].status == TaskStatus.COMPLETED
                    for dep in child_node.dependencies
                )
                if all_deps_done:
                    child_node.mark_ready()
                    logger.info(f"Downstream task '{child_id}' ({child_node.name}) unblocked -> READY.")

        return node

    def mark_failed(self, graph: TaskGraph, task_id: str, error_message: str) -> Optional[TaskNode]:
        """
        Handles task failure and retries.
        If retry count < max_retries, sets back to READY for next cycle.
        If exhausted, transitions to FAILED and cancels dependent downstream tasks.
        """
        node = graph.nodes.get(task_id)
        if not node:
            logger.error(f"Task '{task_id}' not found in graph.")
            return None

        self.running_tasks.discard(task_id)
        node.mark_failed(error_message)

        if node.status == TaskStatus.FAILED:
            logger.warning(f"Task '{task_id}' irrevocably FAILED after max retries: {error_message}")
            self._cascade_cancellation(graph, task_id)
        else:
            logger.info(f"Task '{task_id}' retry scheduled ({node.retry_count}/{node.max_retries}).")

        return node

    def _cascade_cancellation(self, graph: TaskGraph, failed_task_id: str) -> None:
        """Cascades cancellation to all dependent tasks that required this failed task."""
        to_cancel = [child_id for child_id in graph.edges.get(failed_task_id, [])]
        while to_cancel:
            curr = to_cancel.pop(0)
            child = graph.nodes.get(curr)
            if child and child.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                child.status = TaskStatus.CANCELLED
                child.metadata["cancellation_reason"] = f"Dependency '{failed_task_id}' failed."
                logger.warning(f"Cascaded CANCELLED on dependent task '{curr}' ({child.name}).")
                to_cancel.extend(graph.edges.get(curr, []))

    def is_finished(self, graph: TaskGraph) -> bool:
        """Returns True if the entire graph has finished executing (completed, failed, or cancelled)."""
        if len(self.running_tasks) > 0:
            return False
        for node in graph.nodes.values():
            if node.status in (TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.BLOCKED):
                return False
        return True

