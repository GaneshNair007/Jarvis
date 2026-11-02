"""
JARVIS Task Service
Coordinates task execution transitions, dependency satisfaction, tool telemetry,
and real-time Redis agent updates.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models.task import TaskModel
from jarvis.db.events import event_bus, TaskCreatedEvent, TaskCompletedEvent
from jarvis.db.redis_state import redis_state_store
from jarvis.core.logger import get_logger

logger = get_logger("services.task")


class TaskService:
    """Service layer managing task execution states and live Redis status."""

    def __init__(self, uow_factory=UnitOfWork):
        self.uow_factory = uow_factory

    def get_ready_unblocked_tasks(self, task_graph_id: uuid.UUID) -> List[TaskModel]:
        """Queries database for all tasks whose dependencies are 100% satisfied."""
        with self.uow_factory() as uow:
            unblocked = uow.tasks.get_unblocked_tasks(task_graph_id)
            uow.commit()
            return unblocked

    def start_task(
        self,
        task_id: uuid.UUID,
        agent_name: str,
        department: str,
    ) -> Optional[TaskModel]:
        """Transitions task to RUNNING, records assignment, and updates Redis live status."""
        with self.uow_factory() as uow:
            task = uow.tasks.update_task_status(task_id, "RUNNING")
            if task:
                task.assigned_agent = agent_name
                # Find or register agent
                agent = uow.agents.get_agent_by_key(agent_name)
                if agent:
                    uow.assignments.assign_task(task_id=task.id, agent_id=agent.id)

                uow.commit()

                # Update live Redis state
                redis_state_store.set_agent_status(
                    department=department,
                    agent_name=agent_name,
                    status="RUNNING",
                    current_task=task.name,
                    progress=10,
                )
                logger.info(f"Task '{task.name}' ({task.id}) started by [{agent_name}].")
            return task

    def complete_task(
        self,
        task_id: uuid.UUID,
        outputs: Dict[str, Any],
        tool_name: str = "agent_executor",
        duration_seconds: float = 0.5,
    ) -> Optional[TaskModel]:
        """Transitions task to COMPLETED, records execution audit, publishes event, and clears Redis."""
        with self.uow_factory() as uow:
            task = uow.tasks.update_task_status(task_id, "COMPLETED", outputs=outputs)
            if task:
                # Find agent
                agent_id = None
                if task.assigned_agent:
                    ag = uow.agents.get_agent_by_key(task.assigned_agent)
                    if ag:
                        agent_id = ag.id

                # Record execution
                uow.executions.record_execution(
                    task_id=task.id,
                    tool_name=tool_name,
                    input_data=task.metadata_json or {},
                    output_data=outputs,
                    status="SUCCESS",
                    execution_time=duration_seconds,
                    agent_id=agent_id,
                )

                # Record memory if insights exist
                uow.memories.store_memory(
                    category=task.department,
                    content={"task_name": task.name, "outputs": outputs},
                    source_task_id=task.id,
                    goal_id=task.goal_id,
                )

                uow.commit()

                # Publish domain event
                event_bus.publish(TaskCompletedEvent(
                    task_id=str(task.id),
                    task_name=task.name,
                    department=task.department,
                    agent_id=task.assigned_agent or "unassigned",
                    outputs=outputs,
                ))

                # Update live Redis state
                if task.assigned_agent:
                    redis_state_store.set_agent_status(
                        department=task.department,
                        agent_name=task.assigned_agent,
                        status="IDLE",
                        current_task="completed",
                        progress=100,
                    )

                logger.info(f"Task '{task.name}' ({task.id}) marked COMPLETED.")
            return task
