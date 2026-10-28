"""
JARVIS Task Lifecycle State Machine
Enforces strict transitions:
  NEW -> TRIAGED -> PLANNED -> POLICY_CHECK -> QUEUED -> RUNNING -> VERIFYING -> COMPLETED / FAILED / REJECTED
"""

import time
from typing import Dict, Any, Optional, Set
from pydantic import BaseModel, Field

class TaskState(BaseModel):
    task_id: str
    current_status: str = "NEW"
    history: list = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class TaskStateMachine:
    VALID_TRANSITIONS: Dict[str, Set[str]] = {
        "NEW": {"TRIAGED", "REJECTED", "FAILED"},
        "TRIAGED": {"PLANNED", "POLICY_CHECK", "FAILED"},
        "PLANNED": {"POLICY_CHECK", "FAILED"},
        "POLICY_CHECK": {"QUEUED", "RUNNING", "REJECTED", "FAILED"},
        "QUEUED": {"RUNNING", "FAILED"},
        "RUNNING": {"VERIFYING", "COMPLETED", "FAILED"},
        "VERIFYING": {"COMPLETED", "FAILED"},
        "COMPLETED": set(),
        "FAILED": {"NEW"}, # Allow retry
        "REJECTED": {"NEW"} # Allow re-submission
    }

    def __init__(self):
        self.tasks: Dict[str, TaskState] = {}

    def create_task(self, task_id: str, initial_status: str = "NEW") -> TaskState:
        state = TaskState(task_id=task_id, current_status=initial_status)
        state.history.append({"status": initial_status, "timestamp": time.time(), "reason": "Task initialized"})
        self.tasks[task_id] = state
        return state

    def transition(self, task_id: str, new_status: str, reason: str = "") -> TaskState:
        if task_id not in self.tasks:
            self.create_task(task_id)

        task = self.tasks[task_id]
        current = task.current_status

        if new_status not in self.VALID_TRANSITIONS.get(current, set()):
            raise ValueError(f"Illegal state transition from {current} to {new_status} for task {task_id}")

        task.current_status = new_status
        task.updated_at = time.time()
        task.history.append({"status": new_status, "timestamp": task.updated_at, "reason": reason})
        return task

    def get_task(self, task_id: str) -> Optional[TaskState]:
        return self.tasks.get(task_id)

# Singleton State Machine
state_machine = TaskStateMachine()
