"""Chainlit-inspired Step Telemetry and Streaming Manager for Project Jarvis.

Provides real-time execution step telemetry, parent-child task hierarchy,
tool execution tracking, and human-in-the-loop approval status reporting.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import uuid

from jarvis.core.logger import get_logger

logger = get_logger("core.telemetry")


class ExecutionStep:
    """Represents a single granular execution step in an agent run."""

    def __init__(
        self,
        name: str,
        step_type: str = "tool",
        parent_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ):
        self.step_id = f"step_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.step_type = step_type
        self.parent_id = parent_id
        self.inputs = inputs or {}
        self.output: Optional[Any] = None
        self.status = "running"
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.error: Optional[str] = None

    def complete(self, output: Any) -> None:
        self.status = "completed"
        self.output = output
        self.end_time = time.time()

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.end_time = time.time()

    def wait_for_approval(self, approval_request: Dict[str, Any]) -> None:
        self.status = "pending_approval"
        self.output = approval_request

    def to_dict(self) -> Dict[str, Any]:
        duration_ms = (
            round((self.end_time - self.start_time) * 1000, 2)
            if self.end_time
            else round((time.time() - self.start_time) * 1000, 2)
        )
        return {
            "step_id": self.step_id,
            "name": self.name,
            "type": self.step_type,
            "parent_id": self.parent_id,
            "status": self.status,
            "inputs": self.inputs,
            "output": self.output,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": duration_ms,
        }


class StepTelemetryManager:
    """Tracks and streams execution steps across running tasks."""

    def __init__(self):
        self._task_steps: Dict[str, List[ExecutionStep]] = {}

    def start_step(
        self,
        task_id: str,
        name: str,
        step_type: str = "tool",
        parent_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> ExecutionStep:
        step = ExecutionStep(name=name, step_type=step_type, parent_id=parent_id, inputs=inputs)
        if task_id not in self._task_steps:
            self._task_steps[task_id] = []
        self._task_steps[task_id].append(step)
        logger.debug("Task %s started step %s (%s)", task_id, name, step.step_id)
        return step

    def get_steps(self, task_id: str) -> List[Dict[str, Any]]:
        steps = self._task_steps.get(task_id, [])
        return [s.to_dict() for s in steps]

    def clear(self, task_id: str) -> None:
        self._task_steps.pop(task_id, None)


# Singleton Telemetry Manager
step_telemetry = StepTelemetryManager()
