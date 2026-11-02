"""
JARVIS Task Graph Engine (DAG Schema V1 & Graph Topology)
Implements the Directed Acyclic Graph (DAG) foundation for goal-to-task decomposition,
dependency resolution, cycle detection, parallel execution layering, and topological sorting.
"""

from __future__ import annotations

from collections import defaultdict, deque
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskNode(BaseModel):
    task_id: str
    name: str
    description: str
    department: str
    assigned_agent: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    parent_goal: str
    dependencies: List[str] = Field(default_factory=list)
    tool_requirements: List[str] = Field(default_factory=list)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def mark_ready(self) -> None:
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.READY

    def mark_running(self, agent_id: Optional[str] = None) -> None:
        self.status = TaskStatus.RUNNING
        if agent_id:
            self.assigned_agent = agent_id

    def mark_completed(self, outputs: Optional[Dict[str, Any]] = None) -> None:
        self.status = TaskStatus.COMPLETED
        if outputs:
            self.outputs.update(outputs)

    def mark_failed(self, error_message: str) -> None:
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.status = TaskStatus.FAILED
        else:
            self.status = TaskStatus.READY  # Back to ready for retry
        self.metadata["last_error"] = error_message


class Goal(BaseModel):
    goal_id: str
    title: str
    description: str
    created_by: str = "ganesh"
    priority: Priority = Priority.HIGH
    tasks: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskGraph(BaseModel):
    goal_id: str
    nodes: Dict[str, TaskNode] = Field(default_factory=dict)
    edges: Dict[str, List[str]] = Field(default_factory=dict)  # source_task -> [target_tasks]

    def add_node(self, node: TaskNode) -> None:
        """Registers a node into the graph."""
        self.nodes[node.task_id] = node
        if node.task_id not in self.edges:
            self.edges[node.task_id] = []
        # Ensure dependencies point edges to this node
        for dep in node.dependencies:
            if dep not in self.edges:
                self.edges[dep] = []
            if node.task_id not in self.edges[dep]:
                self.edges[dep].append(node.task_id)

    def add_edge(self, source_id: str, target_id: str) -> None:
        """Adds a directed edge from source to target (target depends on source)."""
        if source_id not in self.edges:
            self.edges[source_id] = []
        if target_id not in self.edges[source_id]:
            self.edges[source_id].append(target_id)
        if target_id in self.nodes:
            if source_id not in self.nodes[target_id].dependencies:
                self.nodes[target_id].dependencies.append(source_id)

    def is_cyclic(self) -> bool:
        """Kahn's Algorithm for cycle detection. Returns True if DAG has a cycle."""
        in_degree = {task_id: 0 for task_id in self.nodes}
        for u in self.nodes:
            for v in self.edges.get(u, []):
                if v in in_degree:
                    in_degree[v] += 1

        queue = deque([u for u, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            u = queue.popleft()
            visited_count += 1
            for v in self.edges.get(u, []):
                if v in in_degree:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        queue.append(v)

        return visited_count != len(self.nodes)

    def topological_sort(self) -> List[str]:
        """Returns valid topological execution sequence of task IDs."""
        if self.is_cyclic():
            raise ValueError(f"TaskGraph for goal '{self.goal_id}' contains a circular dependency cycle!")

        in_degree = {task_id: 0 for task_id in self.nodes}
        for u in self.nodes:
            for v in self.edges.get(u, []):
                if v in in_degree:
                    in_degree[v] += 1

        queue = deque([u for u, deg in in_degree.items() if deg == 0])
        ordered: List[str] = []

        while queue:
            u = queue.popleft()
            ordered.append(u)
            for v in self.edges.get(u, []):
                if v in in_degree:
                    in_degree[v] -= 1
                    if in_degree[v] == 0:
                        queue.append(v)

        return ordered

    def get_parallel_layers(self) -> List[List[str]]:
        """
        Groups tasks into parallel execution layers / waves.
        Tasks within the same wave have no dependencies on each other and can execute concurrently.
        """
        if self.is_cyclic():
            raise ValueError(f"TaskGraph for goal '{self.goal_id}' contains a circular dependency cycle!")

        in_degree = {task_id: 0 for task_id in self.nodes}
        for u in self.nodes:
            for v in self.edges.get(u, []):
                if v in in_degree:
                    in_degree[v] += 1

        current_layer = [u for u, deg in in_degree.items() if deg == 0]
        layers: List[List[str]] = []

        while current_layer:
            layers.append(sorted(current_layer))
            next_layer = []
            for u in current_layer:
                for v in self.edges.get(u, []):
                    if v in in_degree:
                        in_degree[v] -= 1
                        if in_degree[v] == 0:
                            next_layer.append(v)
            current_layer = next_layer

        return layers

    def get_ready_tasks(self) -> List[TaskNode]:
        """
        Finds all tasks whose dependencies are 100% COMPLETED and whose status
        is currently PENDING or READY.
        """
        ready = []
        for task_id, node in self.nodes.items():
            if node.status in (TaskStatus.PENDING, TaskStatus.READY):
                # Verify all dependencies are completed
                deps_satisfied = True
                for dep_id in node.dependencies:
                    dep_node = self.nodes.get(dep_id)
                    if not dep_node or dep_node.status != TaskStatus.COMPLETED:
                        deps_satisfied = False
                        break
                if deps_satisfied:
                    node.mark_ready()
                    ready.append(node)
                else:
                    node.status = TaskStatus.BLOCKED
            elif node.status == TaskStatus.BLOCKED:
                # Re-check if blockers resolved
                deps_satisfied = all(
                    self.nodes.get(d) and self.nodes[d].status == TaskStatus.COMPLETED
                    for d in node.dependencies
                )
                if deps_satisfied:
                    node.mark_ready()
                    ready.append(node)
        return ready

    def is_completed(self) -> bool:
        """Returns True if every task node in the graph is COMPLETED."""
        if not self.nodes:
            return False
        return all(node.status == TaskStatus.COMPLETED for node in self.nodes.values())

    def has_failed(self) -> bool:
        """Returns True if any task node has irrevocably FAILED."""
        return any(node.status == TaskStatus.FAILED for node in self.nodes.values())

    def get_progress(self) -> Dict[str, Any]:
        """Telemetry progress summary."""
        total = len(self.nodes)
        if total == 0:
            return {"total": 0, "completed": 0, "percentage": 0.0}
        completed = sum(1 for n in self.nodes.values() if n.status == TaskStatus.COMPLETED)
        return {
            "total": total,
            "completed": completed,
            "percentage": round((completed / total) * 100, 1),
            "running": sum(1 for n in self.nodes.values() if n.status == TaskStatus.RUNNING),
            "failed": sum(1 for n in self.nodes.values() if n.status == TaskStatus.FAILED),
            "ready": sum(1 for n in self.nodes.values() if n.status == TaskStatus.READY),
            "pending": sum(1 for n in self.nodes.values() if n.status == TaskStatus.PENDING),
            "blocked": sum(1 for n in self.nodes.values() if n.status == TaskStatus.BLOCKED),
        }
